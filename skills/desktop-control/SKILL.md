---
name: desktop-control
description: 跨平台桌面自动化（Windows / macOS / Linux）：截图、鼠标点击拖拽、键盘输入、窗口枚举与切换、UI 控件树查询。当用户要求"截图"、"点一下"、"帮我操作某个软件"、"在某某窗口里输入"、"computer use"、"桌面自动化"、"GUI 自动化"，或任何需要看见并控制图形界面才能完成的任务时使用。
---

# 桌面控制 skill

用统一的命令行控制图形界面。CLI 在三个平台上完全一致，脚本按 `sys.platform` 自动选择后端。

## 什么时候用

- 任务的目标程序没有 API、只有图形界面
- 需要看屏幕才能判断下一步（截图 → 判断 → 操作 → 再截图）
- 用户明确让你"操作一下"某个本地软件

**不要**用它做有 API 的事情。HTTP 接口、命令行工具永远比模拟点击可靠。

## 依赖

| 平台 | 必需 | 可选（增强） |
|---|---|---|
| Windows | `python 3.8+`、`pillow`、`pywin32`、PowerShell 7 | — |
| macOS | `python 3.8+`、`pillow`、`pyobjc-framework-Quartz` | `pyobjc-framework-ApplicationServices`（控件树） |
| Linux | `python 3.8+`、`pillow`、`xdotool` | `scrot`/`imagemagick`/`grim`（截图）、`pyatspi`（控件树） |

安装：

```bash
pip install pillow pywin32          # Windows
pip install pillow pyobjc-framework-Quartz   # macOS
sudo apt install xdotool scrot      # Linux (X11)
```

macOS 首次使用必须在「系统设置 → 隐私与安全性」里给终端勾选 **辅助功能** 和 **屏幕录制**，否则输入和截图会被静默拒绝。

## 命令

所有命令形如 `python scripts/desk.py <动作> [参数]`。

```
screen                                       显示器 / 分辨率 / DPI
windows                                      窗口列表（* 为前台窗口）
state                                        光标 + 前台窗口
cursor                                       光标坐标
shot    --out a.png [--window Chrome] [--monitor 0] [--scale 0.75]
focus   --window Chrome | --pid 1234 | --hwnd 5678
move    --x 100 --y 200
click   [--x 100 --y 200] [--button left|right|middle] [--double] [--window Chrome]
drag    --x 10 --y 10 --x2 300 --y2 300 [--steps 20] [--button left]
scroll  [--delta -120]                       负数向下
type    --text "hello" | --text-file msg.txt  [--delay 20] [--window Chrome]
key     --keys CTRL+S   [--window Chrome]    组合键
keydown --keys CTRL       keyup --keys CTRL  按下/抬起分离
ui-dump --window Chrome [--type Button] [--limit 100]
ui-click --window Chrome --name "确定"
selftest                                     后端自检
```

窗口定位优先级：`--hwnd` > `--pid` > `--window <标题子串>`。

## 推荐工作流

```
1. desk.py windows                    # 有哪些窗口
2. desk.py shot --scale 0.75          # 看一眼现状
3. <读图，判断位置>
4. desk.py focus --pid 1234           # 先把目标切到前台
5. desk.py click --x 500 --y 300
6. desk.py shot                       # 再确认结果
```

**每一步都要截图确认**，不要连续盲操作。GUI 的状态和你以为的经常不一样。

## 踩过的坑（务必遵守）

1. **先 focus 再 click。** 坐标点击打的是屏幕最上层的窗口；目标不在前台时，点击会落到别的窗口上。`focus` 之后要校验前台确实切过去了。

2. **中文字符串走 `--text-file`。** 从 bash 把中文传给 Python 时编码会被破坏，命令行参数里的中文可能变成乱码。写进 UTF-8 文件再用 `--text-file`。

3. **窗口名也尽量别用中文当参数。** 同上。用 `--pid` 或 `--hwnd` 定位，或者让脚本内部自己去匹配标题。

4. **发送类操作先展示再执行。** 点击发送/提交/删除/付款之前，先截图确认收件人和内容，让用户点头。

5. **不要连点。** 两次操作之间留出渲染时间（0.3–1 秒），否则第二次点到的还是旧界面。

## 平台差异

| 能力 | Windows | macOS | Linux (X11) | Linux (Wayland) |
|---|---|---|---|---|
| 截图 | Pillow + DWM 边界 | `screencapture` | scrot/import/Pillow | `grim` |
| 鼠标键盘 | `SendInput` / `mouse_event` | Quartz CGEvent | `xdotool` | `ydotool`（需 uinput 权限） |
| 窗口枚举 | `EnumWindows` | `CGWindowList` | `xdotool search` | 受限 |
| 控件树 | UIAutomation（PowerShell） | Accessibility API（部分） | AT-SPI（需 pyatspi） | AT-SPI |
| 按名点击 | ✅ | ❌ 用坐标 | ❌ 用坐标 | ❌ |

Wayland 下 `xdotool` 看不到其他客户端，输入需要 `ydotool` 且要给它 uinput 权限，截图用 `grim`。这是协议本身的限制，不是实现问题。

## 已知限制

- **没有隔离**。操作直接作用于真实桌面，点错是真实的。高风险的探索性任务应该先考虑虚拟机或沙箱。
- 受 DRM 保护的内容（部分视频播放器、安全桌面）截不到，会是黑图。
- UAC / 提权弹窗无法自动确认，必须人工点。
- 坐标点击对界面变化敏感；能用 `ui-click` 按控件名点就别用坐标。

## 自检

```bash
python scripts/desk.py selftest        # 后端基本能力
python scripts/selftest_live.py        # 只做截图和光标移动，不会打字或点击
```

`selftest_live.py` 是安全的，可以在别人正在用的机器上跑。
