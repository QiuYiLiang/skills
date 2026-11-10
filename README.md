# skills

给 Claude Code 用的技能集合。每个技能是一个目录，里面有 `SKILL.md`（元数据 + 使用说明）和可选的 `scripts/`。

技能不是插件，就是一段能被检索到的说明文档：Claude 在遇到匹配的任务时会读到 `SKILL.md`，按里面的流程调用脚本。所以这里的重点是**把踩过的坑写清楚**，而不是堆功能。

## 技能列表

| 技能 | 说明 |
|---|---|
| [desktop-control](desktop-control/) | 跨平台桌面自动化：截图、鼠标、键盘、窗口、控件树。Windows / macOS / Linux |

## 安装

技能目录放到这两个位置之一即可被发现：

```bash
# 全局，所有项目可用
~/.claude/skills/<skill-name>/

# 或者只在某个项目里可用
<project>/.claude/skills/<skill-name>/
```

举例（Windows，用目录联接避免两处副本漂移）：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\desktop-control" `
         -Target "C:\workspace\skills\skills\desktop-control"
```

macOS / Linux：

```bash
ln -s /path/to/skills/skills/desktop-control ~/.claude/skills/desktop-control
```

装好后重启 Claude Code，用 `/help` 或直接提需求就能触发。

## 目录结构

```
skills/                         仓库根
├── .claude-plugin/
│   └── marketplace.json        插件清单（技能仓库管理器读这个）
├── README.md
└── skills/
    └── desktop-control/
        ├── SKILL.md            元数据 + 使用说明（Claude 读这个）
        └── scripts/
            ├── desk.py         统一 CLI，按平台分发
            ├── be_win.py       Windows 后端
            ├── be_mac.py       macOS 后端
            ├── be_linux.py     Linux 后端
            ├── uia_win.ps1     Windows 控件树（UIAutomation）
            └── selftest_live.py 非破坏性自检
```

目录结构遵循 [anthropics/skills](https://github.com/anthropics/skills) 的约定：所有技能放在 `skills/<name>/`，每个技能目录下必须有 `SKILL.md`，frontmatter 至少包含 `name` 和 `description`。

## 验证状态

诚实地标注一下实际跑过什么：

| 后端 | 状态 |
|---|---|
| Windows | ✅ 已实测：截图、点击、拖拽、滚轮、中文输入、组合键、窗口聚焦、UIA 控件定位，以及在微信里完整走通「定位联系人 → 输入 → 发送」 |
| macOS | ⚠️ 未实测。代码按 Quartz / screencapture / Accessibility 的 API 写的，需要在真机上验证 |
| Linux X11 | ⚠️ 未实测。依赖 xdotool，接口是标准的 |
| Linux Wayland | ⚠️ 受限。输入需要 ydotool + uinput 权限，截图用 grim |

macOS 和 Linux 后端欢迎提 issue 或 PR 补齐实测结果。

## 设计取舍

几点不太显然的决定：

- **统一 CLI 而不是三套脚本**。用法一致，迁移平台不用改调用方。
- **按键用各自的底层 API，不用通用库**。`pyautogui` 之类的库在这几个平台上都有坑（DPI、Unicode、Wayland），直接用 `SendInput` / CGEvent / xdotool 更可控。
- **输入做 Unicode 注入而不是模拟按键**。中文、emoji 都能打，不受键盘布局影响。
- **Windows 的控件树借 PowerShell**。UIAutomation 的 .NET 绑定比 Python 的完整；而且这个脚本不含 P/Invoke，不会被 Defender 的 AMSI 拦。
- **不用 PowerShell 做键鼠**。`Add-Type` 里写 `SendInput` + `user32.dll` 是典型的输入注入特征，会被 AMSI 判为恶意内容，这是实测踩到的。

## License

MIT
