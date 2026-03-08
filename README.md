# 动态人格插件 (astrbot_plugin_DynamicPersona)

根据用户消息语义，自动切换 AstrBot 的 LLM 人格。

## 功能特性

- 🧠 **语义感知切换**：通过 Selector LLM 分析用户消息，从配置的人格候选列表中选出最合适的一个
- 🔒 **不干预原生人格**：若当前对话已在 AstrBot 中手动绑定人格，插件自动跳过
- ⚡ **会话级缓存**：可配置缓存条数，减少不必要的 Selector LLM 调用
- ⚙️ **WebUI 配置**：所有配置均可在 AstrBot 管理面板中可视化编辑
- 🛡️ **鲁棒容错**：Selector 调用失败时自动 fallback 到规则列表第一项

## 配置说明

在 AstrBot WebUI → 插件管理 → 动态人格 → 插件配置 中配置以下项目：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | `true` | 是否启用此插件 |
| `selector_provider_id` | 空（跟随会话） | Selector LLM 使用的模型，建议选轻量快速的模型 |
| `inject_mode` | `replace` | 人格注入方式：`replace` 完全替换 / `prepend` 前置追加 |
| `cache_ttl` | `3` | 同一会话中 Selector 结果复用 N 条后才重新选择（0 = 每次都选） |
| `selector_prompt_extra` | 空 | 附加到 Selector 系统提示的额外偏好描述 |
| `persona_rules` | `[]` | 人格规则列表，**至少需要配置 2 条** |

### 配置 persona_rules

每条规则包含两个字段：

- **persona_id**：在 AstrBot 人格管理页面创建的人格 ID，通过下拉框选择
- **scenario_desc**：该人格适合的使用场景描述（自然语言），越具体越准确

**示例**：

| 人格 ID | 场景描述 |
|---------|---------|
| `fun_friend` | 用户进行轻松打趣、玩梗、调侃、情感陪伴等非正式聊天时 |
| `expert_assistant` | 用户提出技术问题、正式请求、学术讨论、工作任务分析时 |

## 工作流程

```
用户消息
    │
    ▼
检查原生人格绑定 ──── 已绑定 ──→ 直接放行（不干预）
    │
    ▼（未绑定）
检查 persona_rules 数量 ─── < 2 条 ──→ 直接放行
    │
    ▼
检查会话缓存 ──── 命中 ──→ 复用缓存人格
    │
    ▼（未命中）
Selector LLM（分析消息语义）
    │
    ▼
选中 persona_id → 注入 system_prompt → LLM 请求
```

## 管理员指令

所有指令需管理员权限。

| 指令 | 说明 |
|------|------|
| `/dp status` | 查看插件状态与当前会话缓存信息 |
| `/dp personas` | 列出 AstrBot 中所有已配置的人格 |
| `/dp reload` | 清空所有会话缓存，下次消息重新由 Selector 选择 |
| `/dp enable` | 启用插件 |
| `/dp disable` | 禁用插件（不影响 AstrBot 原生人格） |

## 注意事项

- 插件需要 AstrBot **>= v4.5.7**（使用了 `llm_generate`、`persona_manager` 等新 API）
- Selector LLM 会产生额外的 token 消耗，建议设置一个轻量模型并合理配置 `cache_ttl`
- 插件的 `on_llm_request` 钩子运行在所有插件的**默认优先级**，如有冲突可联系作者调整

## 版本历史

| 版本 | 说明 |
|------|------|
| v1.3.0 | 初始发布：Selector LLM 动态人格选择 + 会话缓存 + 管理员指令 |
