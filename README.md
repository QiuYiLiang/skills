# skills

给 Claude Code 用的技能集合。这个仓库现在只有一个技能：桌面自动化，走 **Codex Computer Use MCP**，没有本地脚本。

技能本身只是一段能被检索到的说明文档：Claude 遇到匹配任务时读到 `SKILL.md`，然后调用 MCP 提供的工具。所以这里的重点是**把工具怎么用、哪里会错写清楚**。

## 它是什么

`codex-cua` 技能没有自己的实现，它是一份用法说明书，背后是 OpenAI Codex 的 Computer Use 运行时（`@oai/sky`）：

- 感知：窗口截图 + 带索引的可访问性控件树（Windows 用 UI Automation，macOS 用 Accessibility）
- 动作：`SendInput` / CGEvent 模拟输入，或直接改写控件值
- 调用方选动作，**它不规划、不嵌套模型**

## 安装

### 前置

| 平台 | 要求 |
|---|---|
| Windows 10/11 | 可交互桌面会话；官方 ChatGPT/Codex Windows 应用并开启 Computer Use（会装 `%LOCALAPPDATA%\OpenAI\Codex\runtimes\cua_node\`）；Node 18+ |
| macOS 12+ | 已解锁的用户会话；`/Applications/ChatGPT.app` 及其 Computer Use 组件；屏幕录制 + 辅助功能权限 |

### 一、注册 MCP

本仓库根目录的 `.mcp.json` 已经写好，插件方式安装时会自动带进去。手动安装的话：

```bash
claude mcp add -s user codex-cua -- npx -y @jellyfish-p/codex-computer-use-mcp@0.6.2
```

装好后调一次 `list_windows`，返回窗口数组才算接上。MCP 服务也可以用 RS-Nocsi 那套（`github.com/RS-Nocsi/codex-cua-mcp`），工具名一致，但要自己 clone + `npm install && npm run build`，并且它默认自动批准，建议加 `CUA_AUTO_APPROVE=false`。

### 二、装技能

```bash
# 全局，所有项目可用（Windows 用目录联接避免两处副本漂移）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\codex-cua" `
         -Target "C:\workspace\skills\skills\codex-cua"

# macOS / Linux
ln -s /path/to/skills/skills/codex-cua ~/.claude/skills/codex-cua
```

或者整个仓库当插件市场装进去，`.mcp.json` 和技能一起生效。装好后重启 Claude Code。

## 审批

每个应用**首次**被操作时，官方运行时要求审批，适配器通过 MCP elicitation 把请求转给 Claude Code，会弹给用户。**这是默认行为，不要关。**

`CODEX_CUA_AUTO_APPROVE=1` 能跳过它。只在明确知道后果时用，而且不会阻止你自己在合并/发送/付款/删除前先给用户看截图。

## 目录结构

```
skills/                         仓库根（同时是插件根）
├── .claude-plugin/
│   └── marketplace.json        插件清单
├── .mcp.json                   插件自带的 MCP 服务注册（codex-cua）
├── README.md
└── skills/
    └── codex-cua/
        └── SKILL.md            元数据 + 工具用法 + 踩坑（Claude 读这个）
```

## 验证状态

诚实标注一下实际跑过什么（2026-11-10，Windows 11）：

| 能力 | 状态 |
|---|---|
| 连接与工具发现 | ✅ `list_windows` 返回窗口数组，13 个工具可用 |
| 控件树 + 文本 | ✅ `get_window_state(include_text: true)` 在 Tauri/Chromium 窗口上拿到完整层级、`settable` 标记、`Secondary Actions`、`document_text` |
| 截图 | ✅ 运行时截图通道可用 |
| 点击 / 输入 / 按键 / 拖拽 / 设值 | ⚠️ 未实测 |
| macOS 全链路 | ⚠️ 未实测 |
| 真实 Chrome 窗口 | ⚠️ 只验证了树结构，未做完整操作 |

## 设计取舍

- **不自己实现桌面后端。** 之前那套自研 Python 后端（截图、SendInput、UIA、光标叠加、Chromium 扩展）已经删除；Codex 的运行时在控件树和输入模拟上的完成度更高，维护成本在别人那边。
- **按索引操作，不按坐标。** 树里的 `element_index` 比屏幕坐标稳，但它是**一次观测值**，场景一变就要重取。
- **不默认自动批准。** 首次操作每个应用都走官方审批，弹给用户；自动批准要显式开。
- **不隐藏截图成本。** `get_window_state` 默认带截图，`document_text` 又和树内容重复，一个中等窗口能到上万字；能用 `include_screenshot: false` 就关掉。
- **网页没有特殊路径。** 浏览器标签页和别的窗口一样走可访问性树，受遮挡和窗口位置影响；要稳定的页面级操作应该另外做 DOM 方案，这里不做。

## 已知限制

- **没有隔离。** 动作直接作用于真实桌面，点错、发错、删错都是真的。
- **依赖 Codex 私有运行时。** 上游升级可能改路径或协议，没有兼容承诺。
- **受 DRM 保护的内容截不到**；UAC / 提权弹窗无法自动确认。
- 只覆盖 Windows 和 macOS，Linux 不在范围内。

## License

MIT
