"""
动态人格插件 (astrbot_plugin_DynamicPersona)

基于发送者ID匹配人格，支持群组/个人配置。完全替换人格设置（包括 tools、skills、begin_dialogs、custom_error_message 等）。

匹配格式：
- 群ID/发送者ID：精确匹配某个群的某个人（AND关系）
- p_发送者ID：匹配该发送者（私聊或任何群）
- g_群ID：匹配该群所有人
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register


_EVENT_DECISION_KEY = "dynamic_persona_decision"


@dataclass(slots=True)
class MatchCondition:
    group_id: str | None
    sender_id: str | None

    def __str__(self) -> str:
        if self.group_id and self.sender_id:
            return f"{self.group_id}/{self.sender_id}"
        elif self.group_id:
            return f"g_{self.group_id}"
        else:
            return f"p_{self.sender_id}"


@dataclass(slots=True)
class PersonaBinding:
    rule_name: str
    conditions: list[MatchCondition]
    persona_id: str
    provider_id: str
    enabled: bool = True


@dataclass(slots=True)
class PersonaDecision:
    persona_id: str
    provider_id: str = ""
    model_name: str = ""
    source: str = "sender_mapping"

    def to_event_extra(self) -> dict[str, str]:
        return {
            "persona_id": self.persona_id,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "source": self.source,
        }


def parse_match_condition(line: str) -> MatchCondition | None:
    line = line.strip()
    if not line:
        return None

    if "/" in line:
        parts = line.split("/", 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return MatchCondition(group_id=parts[0].strip(), sender_id=parts[1].strip())
    elif line.startswith("p_"):
        sender_id = line[2:].strip()
        if sender_id:
            return MatchCondition(group_id=None, sender_id=sender_id)
    elif line.startswith("g_"):
        group_id = line[2:].strip()
        if group_id:
            return MatchCondition(group_id=group_id, sender_id=None)

    return None


@register(
    "astrbot_plugin_DynamicPersona",
    "xkeyC",
    "基于发送者ID的动态人格插件，支持群组/个人配置，可为不同用户绑定不同人格",
    "3.0.0",
)
class DynamicPersonaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._bindings_cache: list[PersonaBinding] | None = None

    async def initialize(self):
        self._bindings_cache = self._parse_bindings()
        logger.info(
            "[DynamicPersona] loaded enabled=%s bindings=%s",
            self.config.get("enabled", True),
            len(self._bindings_cache),
        )
        for b in self._bindings_cache:
            cond_str = ", ".join(str(c) for c in b.conditions)
            logger.info(
                "[DynamicPersona] rule '%s': [%s] -> %s",
                b.rule_name or "unnamed",
                cond_str,
                b.persona_id,
            )

    def _parse_bindings(self) -> list[PersonaBinding]:
        raw_bindings: list[dict[str, Any]] = self.config.get("persona_bindings", [])
        bindings: list[PersonaBinding] = []
        for item in raw_bindings:
            if not item.get("rule_enabled", True):
                continue
            persona_id = str(item.get("persona_id", "")).strip()
            if not persona_id:
                continue

            conditions_text = str(item.get("match_conditions", "")).strip()
            if not conditions_text:
                continue

            conditions: list[MatchCondition] = []
            for line in conditions_text.split("\n"):
                cond = parse_match_condition(line)
                if cond:
                    conditions.append(cond)

            if not conditions:
                continue

            bindings.append(
                PersonaBinding(
                    rule_name=str(item.get("rule_name", "")).strip(),
                    conditions=conditions,
                    persona_id=persona_id,
                    provider_id=str(item.get("provider_id", "")).strip(),
                    enabled=True,
                )
            )
        return bindings

    def _get_bindings(self) -> list[PersonaBinding]:
        if self._bindings_cache is None:
            self._bindings_cache = self._parse_bindings()
        return self._bindings_cache

    @filter.on_waiting_llm_request()
    async def on_waiting_llm(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        logger.info(
            "[DynamicPersona] on_waiting_llm triggered for sender=%s group=%s",
            sender_id,
            event.get_group_id() or "private",
        )
        if not self._should_handle_event(event):
            logger.info("[DynamicPersona] _should_handle_event returned False")
            return

        if await self._has_forced_persona_binding(event):
            logger.info("[DynamicPersona] _has_forced_persona_binding returned True")
            return

        decision = self._match_sender_to_persona(event)
        self._apply_decision_to_event(event, decision)
        await self._update_session_persona(event, decision)

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        decision = self._get_decision_from_event(event)
        if decision is None:
            return

        try:
            if decision.provider_id:
                event.set_extra("selected_provider", decision.provider_id)
            if decision.model_name:
                event.set_extra("selected_model", decision.model_name)

            logger.info(
                "[DynamicPersona] applied persona=%s provider=%s model=%s",
                decision.persona_id,
                decision.provider_id or "(session-default)",
                decision.model_name or "(provider-default)",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[DynamicPersona] failed to apply persona: %s", exc)

    def _should_handle_event(self, event: AstrMessageEvent) -> bool:
        if not self.config.get("enabled", True):
            return False
        if not (event.message_str or "").strip() and not event.message_obj.message:
            return False
        return True

    async def _has_forced_persona_binding(self, event: AstrMessageEvent) -> bool:
        if not event.is_private_chat():
            return False
        try:
            from astrbot.api import sp

            session_service_config = (
                await sp.get_async(
                    scope="umo",
                    scope_id=str(event.unified_msg_origin),
                    key="session_service_config",
                    default={},
                )
                or {}
            )
            persona_id = str(session_service_config.get("persona_id", "")).strip()
            if persona_id and persona_id != "[%None]" and persona_id != self._get_matched_persona_id(event):
                logger.info(
                    "[DynamicPersona] private session %s already forced to persona %s, skip",
                    event.unified_msg_origin,
                    persona_id,
                )
                return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "[DynamicPersona] failed to inspect forced session persona: %s",
                exc,
            )
        return False

    def _get_matched_persona_id(self, event: AstrMessageEvent) -> str | None:
        bindings = self._get_bindings()
        if not bindings:
            return None

        group_id = event.get_group_id() or ""
        sender_id = event.get_sender_id() or ""

        for binding in bindings:
            for cond in binding.conditions:
                if self._check_condition_match(cond, group_id, sender_id):
                    return binding.persona_id
        return None

    def _match_sender_to_persona(self, event: AstrMessageEvent) -> PersonaDecision | None:
        bindings = self._get_bindings()
        if not bindings:
            return None

        group_id = event.get_group_id() or ""
        sender_id = event.get_sender_id() or ""

        for binding in bindings:
            for cond in binding.conditions:
                if self._check_condition_match(cond, group_id, sender_id):
                    logger.info(
                        "[DynamicPersona] matched rule '%s' condition '%s' -> persona=%s",
                        binding.rule_name or "(unnamed)",
                        str(cond),
                        binding.persona_id,
                    )
                    return self._build_decision_from_binding(binding, event)

        return None

    def _check_condition_match(
        self,
        cond: MatchCondition,
        group_id: str,
        sender_id: str,
    ) -> bool:
        if cond.group_id and cond.sender_id:
            return group_id == cond.group_id and sender_id == cond.sender_id
        elif cond.group_id:
            return group_id == cond.group_id
        elif cond.sender_id:
            return sender_id == cond.sender_id
        return False

    def _build_decision_from_binding(
        self,
        binding: PersonaBinding,
        event: AstrMessageEvent,
    ) -> PersonaDecision:
        provider_id = ""
        model_name = ""

        if binding.provider_id:
            provider = self.context.get_provider_by_id(binding.provider_id)
            if provider is not None:
                provider_id = binding.provider_id
                model_name = getattr(provider, "get_model", lambda: "")() or ""
            else:
                logger.warning(
                    "[DynamicPersona] provider '%s' for persona '%s' not found",
                    binding.provider_id,
                    binding.persona_id,
                )

        if not provider_id:
            provider_id = self._get_current_chat_provider_id(event)
            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
                model_name = getattr(provider, "get_model", lambda: "")() or ""

        return PersonaDecision(
            persona_id=binding.persona_id,
            provider_id=provider_id,
            model_name=model_name,
            source="sender_mapping",
        )

    def _get_current_chat_provider_id(self, event: AstrMessageEvent) -> str:
        try:
            return self.context.get_using_provider(umo=event.unified_msg_origin).id
        except Exception:
            return ""

    def _apply_decision_to_event(
        self,
        event: AstrMessageEvent,
        decision: PersonaDecision | None,
    ) -> None:
        if decision is None:
            return
        if decision.provider_id:
            event.set_extra("selected_provider", decision.provider_id)
        if decision.model_name:
            event.set_extra("selected_model", decision.model_name)
        event.set_extra(_EVENT_DECISION_KEY, decision.to_event_extra())

    async def _update_session_persona(
        self,
        event: AstrMessageEvent,
        decision: PersonaDecision | None,
    ) -> None:
        try:
            from astrbot.api import sp

            existing_config: dict = (
                await sp.get_async(
                    scope="umo",
                    scope_id=str(event.unified_msg_origin),
                    key="session_service_config",
                    default={},
                )
                or {}
            )

            if decision is not None:
                persona_id = decision.persona_id
                existing_config["persona_id"] = persona_id
                logger.info(
                    "[DynamicPersona] set session %s persona to %s for sender %s",
                    event.unified_msg_origin,
                    persona_id,
                    event.get_sender_id(),
                )
            else:
                existing_config.pop("persona_id", None)
                logger.info(
                    "[DynamicPersona] clear session %s persona for sender %s (use default)",
                    event.unified_msg_origin,
                    event.get_sender_id(),
                )

            await sp.put_async(
                scope="umo",
                scope_id=str(event.unified_msg_origin),
                key="session_service_config",
                value=existing_config,
            )
        except Exception as exc:
            logger.error(
                "[DynamicPersona] failed to update session persona: %s",
                exc,
            )

    def _get_decision_from_event(
        self, event: AstrMessageEvent
    ) -> PersonaDecision | None:
        raw = event.get_extra(_EVENT_DECISION_KEY)
        if not isinstance(raw, dict):
            return None
        persona_id = str(raw.get("persona_id", "")).strip()
        if not persona_id:
            return None
        return PersonaDecision(
            persona_id=persona_id,
            provider_id=str(raw.get("provider_id", "")).strip(),
            model_name=str(raw.get("model_name", "")).strip(),
            source=str(raw.get("source", "sender_mapping")).strip() or "sender_mapping",
        )

    @filter.command_group("dp")
    def dp(self):
        """动态人格调度管理"""
        return None

    @dp.command("status")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def dp_status(self, event: AstrMessageEvent):
        bindings = self._get_bindings()
        group_id = event.get_group_id() or "private"
        sender_id = event.get_sender_id() or "unknown"

        lines = [
            "DynamicPersona 状态",
            f"enabled: {self.config.get('enabled', True)}",
            f"active_bindings: {len(bindings)}",
            f"current_group: {group_id}",
            f"current_sender: {sender_id}",
            "",
            "已配置规则:",
        ]
        for b in bindings:
            cond_str = ", ".join(str(c) for c in b.conditions)
            lines.append(f"- [{b.rule_name or 'unnamed'}] {cond_str} -> {b.persona_id}")
        yield event.plain_result("\n".join(lines))

    @dp.command("sessionid")
    async def dp_sessionid(self, event: AstrMessageEvent):
        lines = [
            f"group_id: {event.get_group_id() or 'private'}",
            f"sender_id: {event.get_sender_id() or 'unknown'}",
            f"session_id: {event.message_obj.session_id if event.message_obj else 'unknown'}",
            f"umo: {event.unified_msg_origin}",
            "",
            "匹配格式提示:",
            "- 群ID/发送者ID: 精确匹配某个群的某个人",
            "- p_发送者ID: 匹配该发送者(私聊或任何群)",
            "- g_群ID: 匹配该群所有人",
        ]
        yield event.plain_result("\n".join(lines))

    @dp.command("enable")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def dp_enable(self, event: AstrMessageEvent):
        self.config["enabled"] = True
        self.config.save_config()
        yield event.plain_result("动态人格已启用。")

    @dp.command("disable")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def dp_disable(self, event: AstrMessageEvent):
        self.config["enabled"] = False
        self.config.save_config()
        yield event.plain_result("动态人格已禁用。")

    async def terminate(self):
        self._bindings_cache = None
        logger.info("[DynamicPersona] terminated")
