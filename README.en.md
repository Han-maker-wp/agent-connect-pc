# PC InterConnect

English | [简体中文](README.md)

**Let the AI agent on your PC securely control another Windows PC** — screenshots, clicks, keyboard input, files, PowerShell, the full set, all via MCP (Model Context Protocol).

If you have used android-mcp + ADB to drive an Android phone, this is the **Windows PC edition** of the same idea — a one-click deploy kit for [windows-mcp](https://github.com/CursorTouch/Windows-MCP) (streamable HTTP) plus connection testers and ready-made client configs.

| | Android setup | Windows PC setup (this project) |
|---|---|---|
| Transport | USB / wireless ADB | LAN / Tailscale, streamable HTTP |
| Controlled-side component | ATX (uiautomator) | windows-mcp 0.8.7 (UI Automation) |
| Agent side | android-mcp (14 tools) | windows-mcp (20 tools: Screenshot / Click / Type / PowerShell / FileSystem …) |

> ⚠️ **Authorization notice**: deploy the controlled-side service only on a computer you own or one whose owner has explicitly consented. A remote-control setup hands the whole machine to an AI agent — follow local laws and respect the owner's wishes.

## How it works

```
Controller PC (runs the agent)                Controlled PC (Windows, to be driven)
┌────────────────────────────┐               ┌────────────────────────────────┐
│ Claude Code / Codex / …    │               │ windows-mcp 0.8.7 (autostart)  │
│  └─ MCP entry pc-interconnect HTTP :8808  │  serve --transport             │
│     ├─ native HTTP client ─┼──────────────►│    streamable-http             │
│     └─ or mcp-remote bridge┤  Bearer auth  │    --host 0.0.0.0              │
└────────────────────────────┘               │    --auth-key <generated>      │
                                             └────────────────────────────────┘
Across networks, wrap with Tailscale (WireGuard-encrypted, free) — no public IP needed.
```

## Quick start

### 1) Controlled PC (the one being driven)

**Option A — offline install (recommended: zero network, zero dependencies)**

1. From the [Releases](https://github.com/Han-maker-wp/pc-interconnect/releases) page download `windows-mcp-server.exe` (~56 MB single file with an embedded Python runtime) and put it in the **same folder** as `install_windows_mcp.bat` (USB stick / file transfer, whatever works)
2. On the controlled PC double-click `install_windows_mcp.bat` — **no internet, no uv/Python install, no admin** (only the firewall step wants an admin terminal once)
3. Note the PORT and AUTH KEY printed on screen

**Option B — online install (when you only have the bat)**

The script downloads the official Python 3.14.7 runtime (python-build-standalone) straight from the **npmmirror CDN** (no GitHub involved), extracts it with the built-in bsdtar, installs windows-mcp from the **Tsinghua PyPI mirror** (Aliyun / pypi.org fallbacks), then adds the per-user autostart entry (Bearer auth, bound to `0.0.0.0`) and starts the server immediately. **No uv, no winget, no admin** — works from China without a VPN (needs Windows 10 1809+; first run ~1–2 min).

> After every login a **minimized console window appears — that IS the server**. Closing it stops remote control (intentionally visible, so the machine owner stays in control at all times).

Uninstall: `uninstall_windows_mcp.bat` (removes the autostart entry + firewall rule; to stop the running server just close its console window).

### 2) Controller PC (where your agent runs)

Verify connectivity first:

```bash
python scripts/test_mcp_http_handshake.py http://<controlled-PC-IP>:8808/mcp --auth-key <KEY>
# Lists all 20 tools on success; add --call DisplayInventory for a read-only live call
```

Then hook the server into your agent (any one of these):

| Client | How |
|---|---|
| Claude Code | `claude mcp add --transport http pc-interconnect http://<IP>:8808/mcp --header "Authorization: Bearer <KEY>"` |
| Cursor (`~/.cursor/mcp.json`) | `{"mcpServers": {"pc-interconnect": {"url": "http://<IP>:8808/mcp", "headers": {"Authorization": "Bearer <KEY>"}}}}` |
| OpenCode (`opencode.json`) | `{"mcp": {"pc-interconnect": {"type": "remote", "url": "http://<IP>:8808/mcp", "headers": {"Authorization": "Bearer <KEY>"}}}}` |
| Codex (`config.toml`) | `[mcp_servers.pc-interconnect]` `url = "http://<IP>:8808/mcp"` |
| ZCode / any stdio-only client | mcp-remote bridge (see below) |

**mcp-remote bridge** (works with any stdio-only client; run `npm install -g mcp-remote` first):

```json
"pc-interconnect": {
  "type": "stdio",
  "command": "node",
  "args": [
    "<npm-global-dir>/mcp-remote/dist/proxy.js",
    "http://<IP>:8808/mcp",
    "--header", "Authorization: Bearer <KEY>"
  ],
  "env": { "NO_PROXY": "localhost,127.0.0.1,::1" }
}
```

Pre-verify the bridge chain with `python scripts/test_mcp_stdio_bridge.py http://<IP>:8808/mcp --auth-key <KEY>`.

Want to try it locally first (no remote PC): double-click `run_local_server.bat` and point your client at `http://127.0.0.1:8808/mcp` (loopback needs no auth).

### 3) Cross-network access (works from ANYWHERE — true remote control)

The two PCs just need internet access — same Wi-Fi not required, no public IP needed: wrap both sides in a [Tailscale](https://tailscale.com) network (free tier: 3 users / 100 devices). Each machine gets a `100.x.x.x` virtual IP and they stay connected from any network, WireGuard-encrypted.

**Controlled PC** (after step 1):

1. Double-click `install_tailscale.bat` → auto-install (one UAC prompt) → a browser opens for sign-in (any GitHub / Google / Microsoft account)
2. The script prints this machine's **Tailscale IP (100.x.x.x)** at the end — send it along with PORT and KEY

**Controller PC**: install [Tailscale](https://tailscale.com/download) and sign in with the **same account**, then replace `<controlled-PC-IP>` with the `100.x.x.x` address everywhere.

> The main install script auto-prints the 100.x IP in its final panel if Tailscale is already installed, so all three lines are on one screen.
> Advanced: generate an Auth Key in the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys) and run `install_tailscale.bat <key>` for a fully automatic, browser-free login.

## Security

- **Auth is mandatory by default**: windows-mcp refuses to bind non-loopback addresses without credentials; the deploy script always generates a random Bearer KEY
- **Least privilege (optional)**: `serve` supports `--ip-allowlist "192.168.1.0/24"`, `--exclude-tools "PowerShell,Registry"` (drop the arbitrary-command tools), and TLS (`--ssl-certfile/--ssl-keyfile`) — append them to the autostart command line yourself
- **Across networks**: prefer [Tailscale](https://tailscale.com) (WireGuard-encrypted, and the tailnet removes firewall juggling); in regions where NAT punching fails, use frp + a VPS
- **Rollback**: run `uninstall_windows_mcp.bat` on the controlled PC to remove everything; manual rollback = `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /f` + `netsh advfirewall firewall delete rule name="windows-mcp-8808"`
- **Usage guidance**: never let the agent perform payments; ask the owner before deleting anything; record original values before changing system settings; treat screenshots as sensitive data

## FAQ

- **bat flashes/crashes with mojibake**: the bats in this repo are pure ASCII (safe on any codepage). If you edited one and got `'xxx' is not recognized as an internal or external command`, your bat was saved as UTF-8 with non-ASCII text — cmd parses batch files in the ANSI codepage (GBK on Chinese Windows). Keep bats pure ASCII
- **What is that minimized console window after login**: the windows-mcp server itself (launched by the autostart entry). Keep it open = remote control allowed; close it = control stops immediately. Run `uninstall_windows_mcp.bat` to remove it entirely
- **Online install stuck/slow on downloads**: since v0.3.0 the online install rides China CDNs end to end — the Python runtime comes from npmmirror (ghproxy/GitHub only as fallbacks) and pip packages from the Tsinghua mirror (Aliyun/pypi.org fallbacks), so it works **without a VPN**; the most reliable path is still **Option A's offline exe**, which skips downloads entirely
- **Agent goes blind when the PC is locked** (black screenshots / clicks do nothing): Windows GUI automation needs an active desktop session. Set the controlled PC to "never turn off display + auto logon"; note that an RDP disconnect locks the session
- **UAC elevation prompts**: the agent cannot click the secure desktop — keep elevation steps human-confirmed
- **Clash/proxy users**: if the agent cannot reach the controlled PC, add its IP to the `NO_PROXY` env of the MCP client config (don't touch system proxy variables)
- **Antivirus flags**: windows-mcp is a legit PyPI package (MIT, actively maintained); occasional heuristic false positives — whitelist it

## Credits & license

- Core controlled-side capability comes from [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) (MIT)
- The deploy scripts and test tools in this repo are also [MIT](LICENSE)
