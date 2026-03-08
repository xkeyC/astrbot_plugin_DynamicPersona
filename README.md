# astrbot_plugin_DynamicPersona

AstrBot 动态人格插件是一个高级扩展组件，旨在通过分析用户意图自动切换语言模型的人格设定及其底层服务提供商。

## 核心能力

- **语义路由引擎**：利用 Selector (选择器) 大语言模型分析用户消息，并将其语义意图映射到已配置的人格候选列表中最合适的一项。
- **跨后端调度 (V2 架构)**：在底层拦截 AstrBot 的提供商实例化管线 (`on_waiting_llm_request`)。支持将请求完全路由到不同的大语言模型提供商和特定模型（例如在本地 Ollama 和云端 OpenAI 之间无缝切换）。
- **会话感知缓存**：在每个用户会话中实现可配置的 LRU 风格缓存，最大限度地减少冗余的 Selector 模型调用，降低 API 成本与延迟。
- **原生上下文保留**：当检测到用户的当前 AstrBot 会话已显式绑定了原生人格时，自动跳过动态路由，防止发生冲突。
- **高可用容错**：如果 Selector 模型返回的 JSON 格式无效或遇到网络超时，系统将自动降级并使用规则列表中的第一个人格。

## 配置指南

请前往 AstrBot WebUI -> 插件管理 -> 动态人格 -> 插件配置 中修改以下设置：

### 全局设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 动态人格路由网关的总开关。 | true |
| `session_filter_mode` | 访问控制模式：`disabled` (允许所有会话)、`whitelist` (仅白名单) 或 `blacklist` (仅黑名单)。 | disabled |
| `session_filter_list` | 受访问控制模式限制的群组 ID 或发送者 ID 列表。 | [] |
| `selector_provider_id` | Selector 模型专用的提供商。强烈建议指定一个快速、低延迟的模型。留空则继承当前会话的主提供商。 | 空 |
| `inject_mode` | 系统提示词 (System Prompt) 注入策略：`replace` (完全覆盖) 或 `prepend` (追加在现有提示词之前)。 | replace |
| `cache_ttl` | 在同一会话中复用所选人格的连续消息数。设置为 0 则强制对每条消息重新评估。 | 3 |
| `selector_prompt_extra` | 附加在 Selector 系统提示词末尾的补充指令，用于微调路由判定行为。 | 空 |

### 人格规则 (`persona_rules`)

至少需要定义两个路由场景规则，插件方可激活。

| 字段 | 说明 |
|------|------|
| `rule_enabled` | 切换特定路由规则的激活状态。 |
| `persona_id` | 要应用的目标 AstrBot 人格。可通过原生下拉界面选择。 |
| `provider_id` | (跨后端路由特性) 专用于此人格的大语言模型提供商和具体模型。由 AstrBot 原生 `select_providers` 组件提供下拉支持。留空则使用当前会话的默认模型。 |
| `persona_desc` | 关于该人格角色和能力的简明定义，用于为 Selector 模型提供参考。 |
| `scenario_desc` | 精确的自然语言描述，明确界定触发此人格的上下文条件。 |

## 架构工作流

1. **请求前置拦截钩子 (`on_waiting_llm_request`)**:
   - 评估总开关、会话过滤器以及原生人格绑定状态。
   - 评估会话缓存的有效性。
   - 将用户消息分发至 Selector 模型进行意图分析。
   - 计算目标 `persona_id` 和 `provider_id`。
   - 注入 `event.set_extra("selected_provider")` 和 `event.set_extra("selected_model")` 以强制 AstrBot 框架分配指定的模型后端。

2. **指令注入钩子 (`on_llm_request`)**:
   - 从 AstrBot 的 PersonaManager (人格管理器) 中检索最终的 `system_prompt`。
   - 根据选定的 `inject_mode` 修改即将发出的 ProviderRequest。

## 管理员指令

以下指令需要 AstrBot 的超级管理员 (SuperAdmin) 权限。

| 指令 | 作用 |
|------|------|
| `/dp status` | 打印当前会话的网关状态、缓存深度和激活的路由规则。 |
| `/dp personas` | 获取并列出 AstrBot 环境中所有已注册的人格模板。 |
| `/dp reload` | 清除所有会话的内存缓存，强制在下一次请求时进行全局重新评估。 |
| `/dp enable` | 激活核心路由网关。 |
| `/dp disable` | 停用网关。不会影响原生 AstrBot 的行为。 |
| `/dp sessionid` | 输出当前通道的识别指标（群组 ID、用户 ID、会话 ID），以便配置白名单。 |

## 系统要求

- 最低 AstrBot 版本：**v4.5.7** (必须支持 `event.set_extra` 以及现代化的 `ProviderRequest` 生命周期钩子)。

## 版本历史

- **v2.0.0 (当前版本)**: 重构路由架构。实现前置提供商拦截技术，支持真正的跨引擎扩展。全面支持原生 `select_providers` 组件的联合解析。
- **v1.3.0**: 初始版本。基础的语义场景切换与缓存管理。
