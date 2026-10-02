# AgentConnect-PC

[简体中文](README.md) | English

> **For AI agents**: if you do not know this project, do not guess commands. Read [AGENTS.md](AGENTS.md) in the repository root first. It contains the complete mental model, file map, standard workflows, troubleshooting decision tree, security boundaries, build and release rules. You can also give this repository to your agent and ask it to read `AGENTS.md`, this README, and `agent_connect/` before doing anything.

**AgentConnect-PC lets an AI Agent control another Windows PC through MCP + Tailscale.**

It is not a traditional remote desktop. The controller manages targets, discovers Tailscale peers, verifies MCP, generates client configuration, and hands the target to an AI Agent. The controlled side only runs a small windows-mcp service.

## 1. The model in 30 seconds

```
Controller: AgentConnect CLI / GUI + Tailscale
  ├─ creates a target bundle (single-use Auth Key + Bearer + offline exe)
  ├─ discovers the target's 100.x address
  ├─ verifies MCP initialize / Bearer handshake
  └─ prints Claude / Cursor / OpenCode / Codex / ZCode config
       │ Tailscale WireGuard
       ▼
Controlled PC: install_on_target.bat -> windows-mcp-server.exe :8808
  └─ Screenshot / Click / Type / FileSystem / PowerShell and 20 MCP tools
```

- **Controller**: the PC running the AI Agent and AgentConnect.
- **Controlled PC**: the Windows PC being operated; its owner only receives a folder and double-clicks `install_on_target.bat`.
- **Default transport**: Tailscale 100.x + HTTP MCP + Bearer authentication.
- **Authorization**: deploy only with the owner's explicit consent. Payments/transfers are forbidden; deletion and system changes require owner confirmation and records.

## 2. Controller releases

GitHub Releases provide two Windows x64 assets:

| Asset | Best for | Usage |
|---|---|---|
| `agent-connect-cli-windows-x64.zip` | automation, terminal users, agents | extract and run `agent-connect-cli.exe --help` |
| `agent-connect-gui-windows-x64.zip` | non-technical users | extract and double-click `agent-connect-gui.exe` |

Both are standalone Windows packages: the controller does not need Python, Node, PyInstaller, or an MCP SDK. Each package also contains the controlled-side offline `windows-mcp-server.exe` and deployment templates.

> If the instructions are unclear, **give this repository to your AI Agent** and ask it to connect a Windows PC with AgentConnect-PC. Tell it to read `AGENTS.md` first. Never share `Auth Key`, `Bearer`, or `my-targets/*.env` with anyone except the authorized agent/operator.

## 3. CLI quick start

### 3.1 First-time setup

1. Install and log in to [Tailscale](https://tailscale.com/download/windows) on the controller.
2. Download and extract the CLI zip.
3. For automatic single-use Auth Key generation, save a management token as:

```text
my-targets/tailscale-api.env
TSMGMT_TOKEN=tskey-api-...
```

You can also skip the management token and pass a single-use Auth Key generated in the Tailscale admin console to `new`.

### 3.2 Create a target bundle and connect

```bat
agent-connect-cli.exe new client-1 --auth-key tskey-auth-...
```

Send the entire generated `target-client-1/` folder to the device owner. They only need to:

1. double-click `install_on_target.bat`;
2. approve the administrator prompts;
3. keep the minimized `windows-mcp server` window open.

Wait for the target to join the tailnet and pass MCP verification:

```bat
agent-connect-cli.exe wait client-1 --timeout 3600
```

On success the target `.env` is updated with `TARGET_IP` and `TARGET_HOSTNAME`.

### 3.3 Daily diagnostics and configuration

```bat
agent-connect-cli.exe status
agent-connect-cli.exe ip
agent-connect-cli.exe ping 100.x.y.z
agent-connect-cli.exe netcheck
agent-connect-cli.exe snippets client-1 --client all
```

- `status`: controller and all Tailscale peers.
- `ping`: separates tunnel failures from MCP/firewall failures.
- `netcheck`: NAT, UDP, and DERP diagnosis.
- `snippets`: Claude Code, Cursor, OpenCode, Codex, and ZCode configuration.

Run `agent-connect-cli.exe --help` for the complete command reference.

## 4. GUI quick start

Double-click `agent-connect-gui.exe`:

- see targets from `my-targets/*.env`;
- generate a target bundle and secret archive;
- wait for a target, discover its peer, and verify MCP;
- refresh Tailscale status;
- ping a target and run NAT/DERP diagnostics;
- copy Claude/Cursor/OpenCode/Codex/ZCode configuration snippets.

The GUI does not upload keys to a third party. The Tailscale API is called only when you explicitly configure a management token and use `new`.

## 5. Controlled-side installation

### Recommended: offline mode

The target bundle includes `windows-mcp-server.exe` or can download it from Releases. The target does not need Python, uv, Node, or GitHub access:

1. double-click `install_on_target.bat`;
2. approve at most two administrator prompts;
3. keep the service window open.

### Online fallback

Without the offline exe, `install_windows_mcp.bat` downloads the Python runtime from npmmirror and installs windows-mcp from the Tsinghua PyPI mirror. It does not require uv or winget; it works without a VPN in mainland China on Windows 10 1809+.

## 6. Connect an AI client

After a successful connection, use `snippets` or the GUI's “Copy MCP config”. The essential values are:

```text
http://<target Tailscale IP>:8808/mcp
Authorization: Bearer <BEARER from the target .env>
```

For stdio-only clients, use `mcp-remote`. Example:

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

The repository also contains `tailscale-mcp/server.py`, exposing `ts_status`, `ts_ping`, `ts_netcheck`, `ts_up`, `ts_down`, `ts_ip`, and `ts_version` as MCP tools.

## 7. Build from source

On Windows, use Python 3.14 and a PyInstaller environment:

```bat
uv venv .build-venv --python 3.14
uv pip install --python .build-venv\Scripts\python.exe pyinstaller
python build_controller.py --clean --target-exe release-assets\windows-mcp-server.exe
```

Outputs:

```text
release-staging/agent-connect-cli-windows-x64.zip
release-staging/agent-connect-gui-windows-x64.zip
```

`packaging/*.spec` is the auditable build configuration. The GUI uses Windows' built-in Tkinter; it does not add Qt or Electron.

## 8. Project map

| Path | Role |
|---|---|
| `agent_connect/core.py` | shared Tailscale, target config, Auth Key, MCP probing, and config snippets |
| `agent_connect/cli.py` | controller CLI |
| `agent_connect/gui.py` | controller Tkinter GUI |
| `tailscale-mcp/server.py` | MCP wrapper around the local Tailscale CLI |
| `install_windows_mcp.bat` | controlled-side installer |
| `uninstall_windows_mcp.bat` | controlled-side uninstaller |
| `packaging/*.spec` | CLI/GUI PyInstaller specs |
| `build_controller.py` | creates both release zips |
| `AGENTS.md` | complete operations manual for AI agents |
| `my-targets/` | local secrets and target archives; never commit |

## 9. Security and troubleshooting

- Target missing from `tailscale status`: make sure the target ran its installer and joined the same tailnet.
- `tailscale ping` fails: the target may be powered off/asleep; then inspect Tailscale and the firewall.
- Ping works but MCP returns 401: check the target's `BEARER` in its `.env`.
- Ping works but port 8808 times out: the controlled service window or firewall rule is missing.
- With Clash/proxies, add the target 100.x IP to the MCP client's `NO_PROXY`; do not change system proxy variables.
- Lock screen/RDP disconnects can blind Windows GUI automation because the desktop session is inactive.
- Never commit `my-targets/`, `target-*/`, zips, Auth Keys, Bearer keys, or management tokens.

## 10. Reproduction instructions for AI agents

If you are an AI Agent reading this project:

1. read `AGENTS.md` in full;
2. run `git status` and verify that no real secrets are present;
3. run `agent-connect-cli.exe status` or `python -m agent_connect.cli status`;
4. for a new target, generate a single-use Auth Key and run `new`;
5. send the entire `target-<name>/` folder to the controlled side, then run `wait`;
6. use `snippets` rather than hand-writing Bearer values;
7. follow the owner's authorization, payment prohibition, deletion confirmation, and system-change logging rules.

Do not guess paths or secrets from this README. If uncertain, return to `AGENTS.md` and `agent_connect/core.py`.

## License

The scripts and AgentConnect controller are MIT. Controlled-side capability comes from [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) (MIT).
