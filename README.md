# PC InterConnect

[English](README.en.md) | 简体中文

**让 PC 上的 AI agent 安全地操控另一台 Windows 电脑** —— 截图、点击、键盘输入、文件、PowerShell 全套，通过 MCP（Model Context Protocol）。

One-liner (EN): Let your AI coding agent (Claude Code / Codex / Cursor / OpenCode / ZCode…) control another Windows PC over MCP — a one-click deploy kit for [windows-mcp](https://github.com/CursorTouch/Windows-MCP) (streamable HTTP) plus connection testers and ready-made client configs.

如果你用过 android-mcp + ADB 操控安卓手机，这就是它的 **Windows 电脑版**：

| | 安卓方案 | Windows 电脑方案（本项目） |
|---|---|---|
| 传输通道 | USB / 无线 ADB | 局域网 / Tailscale，streamable HTTP |
| 受控端组件 | ATX (uiautomator) | windows-mcp 0.8.7（UI Automation） |
| Agent 侧 | android-mcp（14 工具） | windows-mcp（20 工具：Screenshot / Click / Type / PowerShell / FileSystem …） |

> ⚠️ **授权声明**：只在你自己拥有、或已获得设备主人明确同意的电脑上部署受控端。远程控制软件的能力等价于把整台电脑交给 agent，请遵守当地法律与对方意愿。

## 工作原理

```
控制端（跑 agent 的电脑）                     受控端（被操控的 Windows 电脑）
┌────────────────────────────┐              ┌────────────────────────────────┐
│ Claude Code / Codex / …    │              │ windows-mcp 0.8.7（登录自启）   │
│  └─ MCP 配置 pc-interconnect│  HTTP :8808 │  serve --transport             │
│     ├─ 原生 HTTP 客户端 ────┼─────────────►│    streamable-http             │
│     └─ 或 mcp-remote 桥接 ──┤  Bearer 认证 │    --host 0.0.0.0              │
└────────────────────────────┘              │    --auth-key <部署时生成>      │
                                            └────────────────────────────────┘
跨网段时套一层 Tailscale（WireGuard 加密，免费）即可，无需公网 IP。
```

## 快速开始

### ① 受控端（被操控的电脑）

**方式一：离线安装（推荐——零网络、零依赖，适合环境不全的电脑）**

1. 在 [Releases](https://github.com/Han-maker-wp/pc-interconnect/releases) 下载 `windows-mcp-server.exe`（约 56MB 单文件，内置 Python 运行时），与 `install_windows_mcp.bat` 放进**同一个文件夹**（U 盘 / 微信传文件均可）
2. 在受控机上双击 `install_windows_mcp.bat`——**不联网、不装 uv/Python、无需管理员**（仅防火墙和可选的 Tailscale 各需一次管理员/登录）；脚本结尾会询问是否一键配置 Tailscale 跨网络（见 ③）
3. 抄下屏幕上的 PORT 和 AUTH KEY

**方式二：在线安装（只有 bat 时）**

脚本从 **npmmirror CDN** 直接下载官方 Python 3.14.7 运行时（python-build-standalone，不经 GitHub）→ 系统自带 bsdtar 解压 → 从**清华 PyPI 镜像**安装 windows-mcp（阿里、官方源自动回退）→ 写入用户级启动项（含 Bearer 认证，绑定 `0.0.0.0`）并立即启动。**全程不需要 uv、winget、管理员**，国内无代理可走通（要求 Win10 1809+，首次约 1–2 分钟）。

> 每次登录后会出现一个**最小化的 windows-mcp 控制台窗口——那就是受控服务本体**，关掉它就停止远程受控（故意保持可见，设备主人随时知情、随时可断）。

卸载：`uninstall_windows_mcp.bat`（删启动项 + 防火墙规则；停止当前服务关掉控制台窗口即可）。

### ② 控制端（跑 agent 的电脑）

先验证连通：

```bash
python scripts/test_mcp_http_handshake.py http://<受控机IP>:8808/mcp --auth-key <KEY>
# 通过后会列出 20 个工具；加 --call DisplayInventory 可实测一次只读调用
```

然后把 server 接进你的 agent（任选其一）：

| 客户端 | 接入方式 |
|---|---|
| Claude Code | `claude mcp add --transport http pc-interconnect http://<IP>:8808/mcp --header "Authorization: Bearer <KEY>"` |
| Cursor（`~/.cursor/mcp.json`） | `{"mcpServers": {"pc-interconnect": {"url": "http://<IP>:8808/mcp", "headers": {"Authorization": "Bearer <KEY>"}}}}` |
| OpenCode（`opencode.json`） | `{"mcp": {"pc-interconnect": {"type": "remote", "url": "http://<IP>:8808/mcp", "headers": {"Authorization": "Bearer <KEY>"}}}}` |
| Codex（`config.toml`） | `[mcp_servers.pc-interconnect]` `url = "http://<IP>:8808/mcp"` |
| ZCode / 其他仅 stdio 客户端 | 用 mcp-remote 桥接（见下） |

**mcp-remote 桥接**（适用于任何只支持 stdio 的客户端，先 `npm install -g mcp-remote`）：

```json
"pc-interconnect": {
  "type": "stdio",
  "command": "node",
  "args": [
    "<npm全局目录>/mcp-remote/dist/proxy.js",
    "http://<IP>:8808/mcp",
    "--header", "Authorization: Bearer <KEY>"
  ],
  "env": { "NO_PROXY": "localhost,127.0.0.1,::1" }
}
```

桥接链路可用 `python scripts/test_mcp_stdio_bridge.py http://<IP>:8808/mcp --auth-key <KEY>` 预先验证。

想先在本机体验（不接远程机）：双击 `run_local_server.bat`，客户端连 `http://127.0.0.1:8808/mcp` 即可（回环免认证）。

### ③ 跨网络访问（不在同一局域网也能连——真正意义上的远程操控）

两台电脑各自上网就行，不用同一 WiFi、不用公网 IP：套一层 [Tailscale](https://tailscale.com) 组网（免费档 3 用户/100 设备），两台机器各领一个 `100.x.x.x` 虚拟 IP，任何网络环境下互通且 WireGuard 加密。

**受控端**（装完 ① 后）：

1. **已内置**：`install_windows_mcp.bat` 结束前会询问「Set up Tailscale now?」——输 `y` 即自动安装（一次 UAC）并弹浏览器登录（GitHub / Google / 微软任一账号）；也可单独双击 `install_tailscale.bat` 补装，或第三个参数传 Auth Key 全自动：`install_windows_mcp.bat <port> <key> <tailscale-auth-key>`
2. 脚本最后会打印这台机器的 **Tailscale IP（100.x.x.x）**——把它和 PORT、KEY 一起发给控制端

**控制端**：安装 [Tailscale](https://tailscale.com/download) 并登录**同一个账号**，之后把所有命令里的 `<受控机IP>` 换成对方的 `100.x.x.x` 即可。

> 主安装脚本结束时若检测到已装 Tailscale，会把 100.x IP 直接打进结果面板，三行信息一次抄齐。
> 进阶：在 [Tailscale 管理台](https://login.tailscale.com/admin/settings/keys)生成 Auth Key 后，`install_tailscale.bat <key>` 可免浏览器全自动登录。

## 安全

- **认证默认强制**：windows-mcp 绑定非回环地址时拒绝无认证运行；部署脚本总是生成随机 Bearer KEY
- **最小权限（可选）**：`serve` 支持 `--ip-allowlist "192.168.1.0/24"`、`--exclude-tools "PowerShell,Registry"`（去掉全权命令执行工具）、TLS（`--ssl-certfile/--ssl-keyfile`）——在计划任务命令行里自行追加
- **跨网段**：首选 [Tailscale](https://tailscale.com)（WireGuard 加密 + 组网即免防火墙）；国内打洞失败可用 frp + VPS
- **回滚**：受控端跑 `uninstall_windows_mcp.bat` 即彻底移除；手动回滚 = `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /f` + `netsh advfirewall firewall delete rule name="windows-mcp-8808"`
- **使用建议**：涉及支付的操作系统上禁止 agent 执行；删除类操作先询问设备主人；更改系统设置前记录原值；屏幕截图属敏感数据，勿外传

## 常见问题

- **双击 bat 闪退/乱码**：本仓库的 bat 全部是纯 ASCII（任何代码页都不会碎）。如果你自己改出了乱码（`'xxx' 不是内部或外部命令`），是 bat 被存成了 UTF-8 带中文——cmd 用 GBK 解析批处理，改回 ASCII 即可
- **登录后弹出的最小化控制台窗口是什么**：是 windows-mcp 服务本体（启动项拉起的）。保持它开着=允许远程受控；关掉=立即停止受控。想彻底移除跑 `uninstall_windows_mcp.bat`
- **在线安装下载卡住/慢**：v0.3.0 起在线安装全程走国内 CDN——Python 运行时来自 npmmirror（ghproxy/GitHub 仅作回退），pip 包走清华源（阿里/官方回退），**无梯子也能走通**；最稳的仍是**方式一离线包**，彻底绕开下载环节
- **锁屏后 agent 失明**（截图黑屏/点击无效）：Windows GUI 自动化需要活跃桌面会话。受控机设置「电源永不熄屏 + 自动登录」，RDP 断开会锁屏，注意错开
- **UAC 提权弹窗**：agent 无法点击安全桌面，提权类操作请人工确认
- **Clash/代理用户**：agent 连不上受控机时，把受控机 IP 加进客户端 MCP 配置的 `NO_PROXY`（别改系统代理变量）
- **杀软报警**：windows-mcp 是 PyPI 正式包（MIT，社区活跃），偶有启发式误报，加白即可

## 致谢与许可

- 核心受控端能力来自 [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)（MIT）
- 本仓库的部署脚本与测试工具同为 [MIT](LICENSE)

> Star 历史不重要，能用就好。有问题提 Issue。
