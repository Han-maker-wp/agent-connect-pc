# AgentConnect-PC

[English](README.en.md) | 简体中文

> **给 AI Agent 的提示**：如果你不熟悉本项目，不要猜命令。请先阅读仓库根目录的 [AGENTS.md](AGENTS.md)，其中包含完整心智模型、文件地图、标准工作流、故障决策树、安全红线、构建和发布规则。你也可以直接把本仓库交给你的 Agent，让它先阅读 `AGENTS.md`、本 README 和 `agent_connect/` 源码，再执行操作。

**AgentConnect-PC 让 AI Agent 通过 MCP + Tailscale 操控另一台 Windows 电脑。**

它不是传统远程桌面：控制端负责为 AI Agent 管理目标机、发现 Tailscale peer、验证 MCP、生成客户端配置；受控端只运行一个简洁的 windows-mcp 服务。

## 1. 30 秒理解

```
控制端：AgentConnect CLI / GUI + Tailscale
  ├─ 生成目标包（一次性 Auth Key + Bearer + 离线受控端 exe）
  ├─ 发现目标机 100.x IP
  ├─ MCP initialize / Bearer 握手验收
  └─ 输出 Claude / Cursor / OpenCode / Codex / ZCode 配置
       │ Tailscale WireGuard
       ▼
受控端：install_on_target.bat → windows-mcp-server.exe :8808
  └─ Screenshot / Click / Type / FileSystem / PowerShell 等 20 个 MCP 工具
```

- **控制端**：运行 AI Agent 的电脑，使用本项目的 CLI 或 GUI。
- **受控端**：被操控的 Windows 电脑，只需接收生成的文件夹，双击 `install_on_target.bat`。
- **默认通道**：Tailscale 100.x 网络 + HTTP MCP + Bearer 认证。
- **授权要求**：只在设备主人明确同意的电脑上部署；支付/转账一律禁止，删除和系统设置变更遵守设备主人确认与留痕要求。

## 2. 控制端发行版

GitHub Releases 提供两个 Windows x64 资产：

| 资产 | 适合谁 | 用法 |
|---|---|---|
| `agent-connect-cli-windows-x64.zip` | 自动化、终端用户、Agent | 解压后运行 `agent-connect-cli.exe --help` |
| `agent-connect-gui-windows-x64.zip` | 非专业用户 | 解压后双击 `agent-connect-gui.exe` |

两个 zip 都是独立运行包，不要求目标电脑安装 Python、Node、PyInstaller 或 MCP SDK。包内还包含受控端离线 `windows-mcp-server.exe` 和安装模板，控制端可以直接生成目标文件夹。

> 如果你看不懂安装步骤，**最推荐的做法是把本仓库交给你的 AI Agent**，明确告诉它“我要使用 AgentConnect-PC 连接一台 Windows 电脑”，让它先阅读 `AGENTS.md`，再按照标准工作流执行。不要把 Auth Key、Bearer 或 `my-targets/*.env` 发给 Agent 以外的任何人。

## 3. CLI 快速开始

### 3.1 第一次配置

1. 在控制端安装并登录 [Tailscale](https://tailscale.com/download/windows)。
2. 下载 CLI zip 并解压。
3. 若要自动生成 Tailscale single-use Auth Key，把管理 token 存为：

```text
my-targets/tailscale-api.env
TSMGMT_TOKEN=tskey-api-...
```

也可以不配置管理 token，直接从 Tailscale 管理台生成 single-use Auth Key，再作为参数传给 `new`。

### 3.2 生成目标包并连接

```bat
agent-connect-cli.exe new client-1 --auth-key tskey-auth-...
```

把生成的 `target-client-1/` **整个文件夹**发给设备主人。对方只需：

1. 双击 `install_on_target.bat`；
2. 在管理员提示中点“是”；
3. 保持最小化的 `windows-mcp server` 窗口打开。

控制端等待目标机上线并自动验收：

```bat
agent-connect-cli.exe wait client-1 --timeout 3600
```

连接成功后，目标配置会写入 `my-targets/client-1.env`，并保存 `TARGET_IP` / `TARGET_HOSTNAME`。

### 3.3 日常诊断和配置

```bat
agent-connect-cli.exe status
agent-connect-cli.exe ip
agent-connect-cli.exe ping 100.x.y.z
agent-connect-cli.exe netcheck
agent-connect-cli.exe snippets client-1 --client all
```

- `status`：查看本机和所有 Tailscale peer。
- `ping`：区分 Tailscale 隧道问题与 MCP/防火墙问题。
- `netcheck`：诊断 NAT、UDP 和 DERP 中继。
- `snippets`：输出 Claude Code、Cursor、OpenCode、Codex、ZCode 配置。

完整命令：

```text
agent-connect-cli.exe --help
agent-connect-cli.exe new --help
agent-connect-cli.exe wait --help
```

## 4. GUI 快速开始

双击 `agent-connect-gui.exe`：

- 左侧显示 `my-targets/*.env` 中的目标；
- “生成目标包”创建目标目录和 Bearer/Auth Key 存档；
- “等待并连接”自动发现 peer、Ping 并验证 MCP；
- “刷新 Tailscale”查看 peer 状态；
- “Ping 目标”和“NAT/DERP 检查”用于诊断；
- “复制 MCP 配置”一次复制 Claude/Cursor/OpenCode/Codex/ZCode 配置片段。

GUI 不会把密钥上传到第三方服务；Tailscale API 只在你主动配置管理 token 并使用 `new` 时调用。

## 5. 受控端安装

### 推荐：离线模式

从 Release 下载 `windows-mcp-server.exe`，或直接使用控制端发行包中自带的副本。目标文件夹由 CLI/GUI 自动生成。受控端不需要 Python、uv、Node 或 GitHub 网络：

1. 双击 `install_on_target.bat`；
2. 同意最多两次管理员提示（Tailscale/防火墙）；
3. 保持服务窗口打开。

### 在线兜底

如果没有离线 exe，`install_windows_mcp.bat` 会从 npmmirror 下载 Python 运行时，再从清华 PyPI 安装 windows-mcp；不依赖 uv/winget，国内无梯子也能工作。要求 Windows 10 1809+。

## 6. AI Agent 接入

连接成功后，CLI 的 `snippets` 或 GUI 的“复制 MCP 配置”会输出配置。核心形态是：

```text
http://<目标机 Tailscale IP>:8808/mcp
Authorization: Bearer <目标配置里的 BEARER>
```

stdio-only 客户端使用 `mcp-remote` 桥接。ZCode 示例：

```json
{
  "type": "stdio",
  "command": "node",
  "args": [
    "<npm-global>/mcp-remote/dist/proxy.js",
    "http://100.x.y.z:8808/mcp",
    "--header",
    "Authorization: Bearer <BEARER>"
  ],
  "env": {"NO_PROXY": "100.x.y.z"}
}
```

仓库还包含 `tailscale-mcp/server.py`：它把 `ts_status`、`ts_ping`、`ts_netcheck`、`ts_up`、`ts_down`、`ts_ip`、`ts_version` 暴露为 MCP 工具。若 Agent 需要自己诊断网络，可以把它作为 stdio MCP server 加入。

## 7. 从源码构建

需要 Windows、Python 3.14 和 PyInstaller 构建环境。推荐使用仓库现有的 `.build-venv`，或新建等价环境：

```bat
uv venv .build-venv --python 3.14
uv pip install --python .build-venv\Scripts\python.exe pyinstaller
python build_controller.py --clean --target-exe release-assets\windows-mcp-server.exe
```

输出：

```text
release-staging/agent-connect-cli-windows-x64.zip
release-staging/agent-connect-gui-windows-x64.zip
```

`packaging/*.spec` 是可审计的构建配置；GUI 使用 Windows 自带 Tkinter，不引入 Qt/Electron。

## 8. 项目结构

| 路径 | 作用 |
|---|---|
| `agent_connect/core.py` | CLI/GUI 共用的 Tailscale、目标配置、Auth Key、MCP 探测和配置片段逻辑 |
| `agent_connect/cli.py` | 控制端终端命令 |
| `agent_connect/gui.py` | 控制端 Tkinter GUI |
| `tailscale-mcp/server.py` | Tailscale 本地 CLI 的 MCP 包装 |
| `install_windows_mcp.bat` | 受控端主安装器 |
| `uninstall_windows_mcp.bat` | 受控端卸载器 |
| `packaging/*.spec` | CLI/GUI PyInstaller 配置 |
| `build_controller.py` | 生成两个发行 zip |
| `AGENTS.md` | 给 AI Agent 阅读的完整运维手册 |
| `my-targets/` | 本地密钥和目标存档，永远不要提交 |

## 9. 安全与故障排查

- `tailscale status` 看不到目标：先确认目标机已运行安装器并加入同一 tailnet。
- `tailscale ping` 不通：目标可能关机/睡眠；再检查 Tailscale 和防火墙。
- Ping 通但 MCP 401：核对目标对应 `.env` 中的 `BEARER`。
- Ping 通但 8808 超时：受控端防火墙规则或服务窗口未运行。
- Clash/代理环境：将目标 100.x IP 加入 MCP 客户端 `NO_PROXY`，不要修改系统代理。
- 锁屏/RDP 断开会让 GUI 自动化失明；这是受控端 Windows 桌面会话限制。
- 不要把 `my-targets/`、`target-*/`、zip、Auth Key、Bearer、管理 token 提交到 Git。

## 10. 给 Agent 的复现指令

如果你是一个正在阅读本项目的 AI Agent，请按以下顺序：

1. 阅读 `AGENTS.md` 全文；
2. 检查 `git status`，确认没有真实密钥；
3. 运行 `agent-connect-cli.exe status` 或 `python -m agent_connect.cli status`；
4. 如果要接入新电脑，优先生成 single-use Auth Key，再运行 `new`；
5. 把整个 `target-<name>/` 交给受控端，运行 `wait` 等待并验证；
6. 只使用 `snippets` 输出的配置，不手写 Bearer；
7. 所有删除、支付、系统设置和敏感数据操作都遵守设备主人授权与项目安全红线。

不要根据 README 猜测未列出的路径或密钥；不确定时回到 `AGENTS.md` 和 `agent_connect/core.py`。

## License

本项目脚本和 AgentConnect 控制端为 MIT；受控端能力来自 [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)（MIT）。
