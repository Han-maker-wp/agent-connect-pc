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

## 7. Advanced: a server as the controller (reverse scenario)

AgentConnect does not care *which* machine runs the agent. Anything that can join the same Tailscale tailnet and speak MCP over HTTP can be the controller — **a cloud server/VPS works fine** and can drive your local Windows PC. Typical use: a 24/7 server agent runs long tasks on your desktop (downloads, file organizing, GUI automation) while you are away.

| Role | In this scenario |
|---|---|
| Agent brain + controller | Linux / Windows server |
| Controlled PC | your local Windows PC (standard controlled-side flow, section 5) |

### Three steps on a Linux server

1. Install Tailscale and join the tailnet:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   tailscale up --authkey tskey-auth-xxxxx      # single-use key, or omit for interactive login
   ```

2. (Optional) use the controller CLI from source — stdlib only, headless-friendly:

   ```bash
   git clone https://github.com/Han-maker-wp/agent-connect-pc.git
   cd agent-connect-pc
   python -m agent_connect.cli status           # Python 3.11+, tailscale on PATH
   ```

   The Windows CLI exe and the Tkinter GUI do not apply to Linux; on a headless server just use the CLI — the agent itself is the management interface.

3. Make the local PC a controlled target and point the server agent at it:
   - run Release's `install_windows_mcp.bat` on the local PC (or `new` a bundle on the server and send it to yourself), note its 100.x IP and Bearer;
   - configure the server agent's MCP client with `http://<local-100.x>:8808/mcp` + `Authorization: Bearer <KEY>`; stdio-only clients use `mcp-remote`; if the server has proxies, add `100.64.0.0/10` (or the target IP) to NO_PROXY.

Verify from the server:

```bash
tailscale ping <local-100.x IP>
curl -sS -X POST http://<local-100.x IP>:8808/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer <KEY>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
```

HTTP 200 means the loop is closed.

### Caveats

- **Keep the local PC awake**: no sleep, autostart entry active, minimized service window open; a locked/asleep PC blinds the GUI tools.
- **Restricted sandbox servers**: Tailscale degrades to DERP relays (TCP 443) when UDP is blocked; if the platform forbids VPNs entirely, fall back to frp/your own tunnel for port 8808 and manage encryption/auth yourself.
- **Trust inversion**: the Bearer key lives on the server — server compromise equals full control of your PC. Harden SSH, consider a Tailscale ACL allowing only server → target:8808, and rotate keys on any suspicion.
- The project red lines (no payments, deletion confirmation, settings logging) apply to server-side agents **just the same**.

## 8. Build from source

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

## 9. Project map

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

## 10. Security and troubleshooting

- Target missing from `tailscale status`: make sure the target ran its installer and joined the same tailnet.
- `tailscale ping` fails: the target may be powered off/asleep; then inspect Tailscale and the firewall.
- Ping works but MCP returns 401: check the target's `BEARER` in its `.env`.
- Ping works but port 8808 times out: the controlled service window or firewall rule is missing.
- With Clash/proxies, add the target 100.x IP to the MCP client's `NO_PROXY`; do not change system proxy variables.
- Lock screen/RDP disconnects can blind Windows GUI automation because the desktop session is inactive.
- Never commit `my-targets/`, `target-*/`, zips, Auth Keys, Bearer keys, or management tokens.

## 11. Reproduction instructions for AI agents

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
