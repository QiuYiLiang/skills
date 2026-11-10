---
name: codex-cua
description: 通过 Codex Computer Use MCP 操作 Windows / macOS 桌面应用：枚举窗口与应用、启动应用、读取窗口的可访问性控件树与截图、按控件索引点击、输入、按键、滚动、拖拽、直接改写控件值、触发控件的次级操作（右键菜单等）。当用户要求"截图"、"点一下"、"帮我操作某个软件"、"在某某窗口里输入"、"computer use"、"桌面自动化"、"GUI 自动化"，或任何需要看见并控制图形界面才能完成的任务时使用。
---

# Codex Computer Use MCP

本技能是 MCP 服务的用法说明书，没有自己的脚本。工具由 `codex-cua` 这个 MCP 服务提供，名字形如 `mcp__codex-cua__<method>`；以插件方式安装时前缀会变成长形式（`mcp__plugin_<插件名>_codex-cua__<method>`），**以当前会话实际列出的工具名为准**。

底层是 OpenAI Codex 的 Computer Use 运行时（`@oai/sky`）：它用 Windows UI Automation / macOS Accessibility 读控件树，用 `SendInput` / CGEvent 模拟输入，用 `Windows.Graphics.Capture` 截图。**调用方选动作，它不规划、不嵌套模型**。

## 工具清单

| 类别 | 工具 | 说明 |
|---|---|---|
| 发现 | `list_windows` | 当前可操作的窗口 |
| 发现 | `list_apps` | 已安装应用 + 其打开的窗口 |
| 发现 | `get_window` | 用之前返回的 `id` 重新拿回窗口对象 |
| 启动 | `launch_app` | 按 `list_apps` 给的 app id 启动 |
| 前置 | `activate_window` | 把窗口切到前台（**不代表编辑器已有焦点**） |
| 感知 | `get_window_state` | 截图 + 带索引的可访问性树，**所有操作的唯一依据** |
| 输入 | `click` | 传 `element_index`，或截图坐标系里的 `x`/`y` |
| 输入 | `type_text` | 在已确认的焦点里输入字面文本（中文直接传，不需要转码文件） |
| 输入 | `press_key` | keysym 组合，如 `Return`、`Tab`、`Control_L+a` |
| 输入 | `set_value` | 对 `settable` 控件直接写值，比点进去全选重打稳 |
| 输入 | `scroll` | 窗口相对坐标 + `scrollX`/`scrollY`，负数向左/上 |
| 输入 | `drag` | 起止坐标 |
| 输入 | `perform_secondary_action` | 执行树里 `Secondary Actions:` 列出的动作，如 `Raise`、`Expand`、`Scroll Up` |

## 核心循环：看 → 选 → 动 → 验

1. **看**。`list_windows` / `list_apps` 定位目标，然后 `get_window_state({window, include_text: true})`。
2. **选**。只从**这一次**的树里选 `element_index`；树里的 `focused_element` 告诉你焦点在哪。
3. **动**。一次只做一个依赖当前画面的动作。要输入就先确认可编辑区域和焦点；如果必须先点一下建立焦点，**先看点击结果再输入**。
4. **验**。动作后再 `get_window_state`。调用没报错不等于目标达成。

## 关键约束（踩过的）

1. **`window` 对象必须原样回传。** 把 `list_windows` / `get_window_state` 返回的那个对象整个塞进去，别用标题重新拼一个。`list_apps` 里带 `windows` 数组的条目也一样。
2. **`element_index` 是一次性观测值，不是句柄。** 页面滚动、窗口移动、弹窗出现、视图切换之后，索引全部作废，必须重新 `get_window_state`。
3. **`get_window_state` 默认带截图，很贵。** 只需要控件结构时传 `include_screenshot: false`；反过来只需要看画面时传 `include_text: false`。
4. **`document_text` 和 `accessibility.tree` 内容高度重复。** 实测一个中等窗口两者各几 KB，一次调用能到上万字。别对同一个窗口反复全量取，操作后只取需要的那部分。
5. **截图坐标是窗口相对的，不是屏幕绝对坐标。** 别拿系统截图工具量出来的屏幕坐标去点；要坐标就从这一次的截图里量，并带上 `screenshotId`。
6. **切前台 ≠ 有焦点。** `activate_window` 之后还要看 `focused_element`；很多应用要先点进编辑区才能打字。
7. **模态框往往是新窗口。** 弹窗出现后重新 `list_windows`，选新返回的窗口对象，别在旧窗口上继续点。
8. **动作结果未知时先看再做。** 超时、连接失败之后不要重放同一个输入——它可能已经执行了两次。先 `get_window_state` 判断。
9. **不要连点。** 两次状态相关的操作之间要重新取状态；同一棵树上连续点两个索引，第二个经常已经失效。
10. **用户按 Esc 或叫停就立刻停止输入。** 恢复前先重新观测。

## 审批

- 每个应用**首次**被操作时，官方运行时要求审批，适配器把请求转发给 MCP 客户端。
- `CODEX_CUA_AUTO_APPROVE=1` 会跳过这个审批。合并/发送/付款/删除这类动作，即使开了自动批准，也应先取 `snap` 或截图给用户确认。
- 屏幕上的 overlay 会显示 `<CUA_AGENT_NAME> is using your computer`，这是给用户看的"谁在操作"提示，不是我们的界面。

## 安装与前置

| 平台 | 要求 |
|---|---|
| Windows 10/11 | 可交互桌面会话；官方 ChatGPT/Codex Windows 应用并开启 Computer Use（会装 `%LOCALAPPDATA%\OpenAI\Codex\runtimes\cua_node\`）；Node 18+ |
| macOS 12+ | 已解锁的用户会话；`/Applications/ChatGPT.app` 及其 Computer Use 组件；屏幕录制 + 辅助功能权限 |

MCP 用 stdio 启动：

```bash
npx -y @jellyfish-p/codex-computer-use-mcp
```

装好后调一次 `mcp__codex-cua__list_windows` 验证；返回窗口数组才算接上。

## 平台差异

| 能力 | Windows | macOS |
|---|---|---|
| 感知 | 窗口级：截图 + UIA 树（带 `element_index`） | 应用级方法（`get_app_state` 一类），索引规则不同 |
| 按索引操作 | ✅ `click` / `set_value` / `perform_secondary_action` | 以实际工具 schema 为准 |
| 次级操作 | ✅ 树里 `Secondary Actions:` 列出的都能触发 | 视控件而定 |
| 工具数量 | 13 个 | 10 个，名字不同 |

**以运行时返回的工具 schema 为准**，不要凭本文假设参数。

## 已知限制

- **没有隔离。** 动作直接作用于真实桌面，点错、发错、删错都是真的。
- **网页没有 DOM 路径。** 浏览器标签页和别的窗口一样走可访问性树 + 坐标；受遮挡、窗口位置、`chrome://` 等内部页影响。需要按页面结构稳定操作的场合它不比坐标点击好多少。
- **依赖 Codex 私有运行时。** 上游升级可能改路径或协议，没有兼容承诺；`list_windows` 突然失败先查 Codex 应用有没有更新。
- **受 DRM 保护的内容截不到**；UAC / 提权弹窗无法自动确认。
- **多显示器 / 高 DPI** 下坐标换算由运行时处理，跨屏拖拽仍需实测确认。
