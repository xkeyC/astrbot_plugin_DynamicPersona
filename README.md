# DynamicPersona

`astrbot_plugin_DynamicPersona` 是一个 AstrBot 插件。

> Fork 自 [KirisameLonnet/astrbot_plugin_DynamicPersona](https://github.com/KirisameLonnet/astrbot_plugin_DynamicPersona)
> 
> 原版使用 LLM 动态决定人格，本 fork 改为基于用户关系表的配置方式，用于控制 MCP tools 的权限，或针对某一组（或单个）用户使用特定的人格。

## 功能

- 基于群ID和发送者ID匹配人格
- 简洁的多行匹配条件格式
- **完全替换人格设置**：包括 system_prompt、tools、skills、begin_dialogs、custom_error_message 等
- 可用于控制 MCP tools 的权限（通过人格的 tools 配置）
- 切换人格时可同步切换到该人格绑定的对话模型配置

## 匹配格式

在多行编辑框中，每行一个匹配条件：

| 格式 | 说明 | 示例 |
|------|------|------|
| `群ID/发送者ID` | 精确匹配某个群的某个人（AND关系） | `12345678/87654321` |
| `p_发送者ID` | 匹配该发送者（私聊或任何群） | `p_11111111` |
| `g_群ID` | 匹配该群所有人 | `g_12345678` |

每行条件任一匹配即生效。

## 安装

将插件放入 AstrBot 的插件目录：

```bash
AstrBot/data/plugins/astrbot_plugin_DynamicPersona
```

然后在 AstrBot 中重载或启用插件。

## 使用场景

### 场景1：控制 MCP Tools 权限

为不同用户配置不同人格，每个人格设置不同的 tools 权限：

```
VIP 用户（可使用所有工具）：
匹配条件：p_11111111
人格配置：tools = all（使用所有工具）

普通用户（限制工具）：
匹配条件：g_12345678
人格配置：tools = ["search", "weather"]（仅使用指定工具）
```

### 场景2：为特定用户使用专属人格

```
管理员（使用管理员人格）：
匹配条件：p_88888888
人格配置：admin_persona（具备更多能力和权限）

普通成员（使用默认人格）：
匹配条件：g_12345678
人格配置：default_persona
```

### 场景3：精确控制某群某用户

```
群管理员：
匹配条件：12345678/88888888
人格配置：group_admin_persona
```

## 使用前准备

在配置本插件前，请先在 AstrBot 中完成以下准备：

1. 在人格管理中创建好需要切换的 AstrBot 人格（配置好 tools、skills、begin_dialogs、custom_error_message 等）
2. 在 Provider 页面配置好需要使用的对话模型条目
3. 确认这些模型条目可以正常工作

## 配置步骤

### 1. 启用插件

在插件配置中将 `enabled` 设为 `true`。

### 2. 添加绑定规则

在 `persona_bindings` 中添加规则：

- `rule_enabled`：是否启用该规则
- `rule_name`：规则名称（可选，用于日志识别）
- `match_conditions`：匹配条件（每行一个）
- `persona_id`：匹配成功时使用的人格
- `provider_id`：该人格使用的对话模型配置（可选）

## 配置示例

### 示例1：为多个用户绑定同一人格

```
匹配条件：
p_11111111
p_22222222
g_12345678

关联人格：vip_persona
```

以上配置表示：发送者 11111111 或 22222222 或群 12345678 的所有人，都将使用 vip_persona 人格。

### 示例2：精确匹配某个群的特定用户

```
匹配条件：
12345678/87654321

关联人格：admin_persona
```

以上配置表示：只有群 12345678 中的发送者 87654321 才会使用 admin_persona 人格。

### 示例3：多规则配置

规则1：
```
匹配条件：
g_11111111
g_22222222

关联人格：test_group_persona
```

规则2：
```
匹配条件：
p_33333333

关联人格：special_user_persona
```

规则按顺序匹配，首次匹配成功即停止。

## 完全替换人格

插件会**完全替换**匹配到的人格设置，包括：

- **system_prompt**：完全替换为该人格的系统提示词
- **tools**：根据人格配置设置可用工具（None=全部工具，空列表=无工具，列表=指定工具）
- **skills**：根据人格配置设置可用技能
- **begin_dialogs**：注入人格的预设对话示例
- **custom_error_message**：设置人格的自定义错误回复

## 管理命令

插件提供以下命令：

- `/dp status`：查看当前插件状态和规则概要
- `/dp enable`：启用插件
- `/dp disable`：禁用插件
- `/dp sessionid`：查看当前会话相关 ID 及匹配格式提示

其中部分命令需要管理员权限。

## 重要限制

- 如果当前会话被 AstrBot 的会话规则强制绑定人格，插件会默认跳过
- 规则按顺序匹配，首次匹配成功即停止
- 本插件依赖 AstrBot 现有的人格与 Provider 配置能力

## 排错

### 没有发生人格切换

检查以下内容：

- 插件是否启用
- `persona_id` 是否在 AstrBot 中真实存在
- 当前会话是否被会话规则强制绑定了固定人格
- 匹配条件格式是否正确（使用 `/dp sessionid` 查看当前 ID）

### 没有发生模型切换

检查以下内容：

- 规则中的 `provider_id` 是否已选择
- 该 `provider_id` 是否对应 AstrBot 中已存在的对话模型条目

## 版本说明

- **v3.0.0**：Fork 自原版，移除 LLM 动态选择功能，改为基于用户关系表的配置方式，支持简洁的多行匹配条件格式，完全替换人格设置
