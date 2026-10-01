"""Lightweight stdio MCP server wrapping the Tailscale CLI.

Lets an AI agent manage the machine's Tailscale VPN conversationally
instead of hand-running CLI commands - the missing piece of the
PC Interconnect deployment loop: ts_status finds a newly deployed
peer's 100.x.x.x IP, ts_ping verifies the tunnel, then the agent
points the pc-interconnect MCP config at that IP itself.

Protocol: newline-delimited JSON-RPC 2.0 over stdio (MCP stdio transport).
Python stdlib only (same style as this project's other MCP servers).

Tools:
  ts_status()    -> installed/running state, self device (name, 100.x IPs),
                    peer list (name, IP, online, OS) - the deploy-loop workhorse
  ts_ip()        -> this machine's Tailscale IPv4
  ts_ping(peer)  -> one ping to a peer (IP or MagicDNS name); tunnel check
  ts_netcheck()  -> NAT type / DERP reachability probe (China NAT diagnosis)
  ts_up(...)     -> bring the VPN up (optional --authkey/--hostname);
                    STATE CHANGE, on Windows may need an admin/UAC
  ts_down()      -> bring the VPN down; STATE CHANGE, may need admin
  ts_version()   -> tailscale version

If the CLI is not installed, every tool returns an install hint instead
of failing cryptically. State-changing tools are also scriptable on a
REMOTE machine through pc-interconnect's PowerShell tool.
"""
import json
import os
import shutil
import subprocess
import sys

TS_FALLBACK = r"C:\Program Files\Tailscale\tailscale.exe"


def _ts_bin():
    p = shutil.which("tailscale")
    if p:
        return p
    return TS_FALLBACK if os.path.isfile(TS_FALLBACK) else None


def _ts(args, timeout=45):
    """Run a tailscale CLI command. Returns (ok, stdout, stderr)."""
    bin_ = _ts_bin()
    if not bin_:
        return False, "", ("tailscale CLI not found on this machine.\n"
                           "Install it first:\n"
                           "  winget install Tailscale.Tailscale\n"
                           "  (or the MSI from https://pkgs.tailscale.com/stable )\n"
                           "After install, log in once: tailscale up")
    try:
        p = subprocess.run([bin_] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode == 0, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return False, "", "[timeout after %ss]" % timeout
    except Exception as e:
        return False, "", "%s: %s" % (type(e).__name__, e)


def _text(lines_or_text):
    if isinstance(lines_or_text, str):
        text = lines_or_text.strip() or "(no output)"
    else:
        text = "\n".join(lines_or_text).strip() or "(no output)"
    return [{"type": "text", "text": text}]


def tool_status():
    # a broken/starting tailscaled makes the CLI retry for ~25-40s before
    # surfacing its own error - allow it to come through instead of timing out
    ok, out, err = _ts(["status", "--json"], timeout=120)
    if not ok:
        return _text((err or out).splitlines())
    try:
        d = json.loads(out)
    except Exception:
        return _text(["status --json returned non-JSON output:", out[:500]])
    self_d = d.get("Self") or {}
    peers = []
    for p in (d.get("Peer") or {}).values():
        ips = p.get("TailscaleIPs") or []
        peers.append({"host": p.get("HostName"),
                      "ip": ips[0] if ips else None,
                      "online": p.get("Online"),
                      "os": p.get("OS")})
    summary = {
        "installed": True,
        "backend_state": d.get("BackendState"),
        "self": {"host": self_d.get("HostName"),
                 "tailscale_ips": self_d.get("TailscaleIPs") or [],
                 "online": self_d.get("Online")},
        "peers": peers,
        "hint": ("deploy loop: point the pc-interconnect MCP config at a "
                 "peer's 100.x.x.x ip, then ts_ping it to verify"),
    }
    return [{"type": "text",
             "text": json.dumps(summary, ensure_ascii=False, indent=2)}]


def tool_ip():
    ok, out, err = _ts(["ip", "-4"])
    if not ok:
        return _text((err or out).splitlines())
    return _text(out.splitlines())


def tool_ping(peer):
    if not peer:
        return _text("[ERROR] peer required (100.x.x.x ip or MagicDNS name)")
    ok, out, err = _ts(["ping", "-c", "1", peer], timeout=60)
    return _text((out + ("\n" + err if err.strip() else "")).splitlines())


def tool_netcheck():
    ok, out, err = _ts(["netcheck"], timeout=90)
    return _text((out + ("\n" + err if err.strip() else "")).splitlines())


def tool_up(authkey=None, hostname=None):
    args = ["up"]
    if authkey:
        args += ["--authkey", authkey]
    if hostname:
        args += ["--hostname", hostname]
    ok, out, err = _ts(args, timeout=180)
    if not ok:
        hint = ((err or out).splitlines() +
                ["note: on Windows this may need an admin terminal / UAC;"])
        return _text(hint)
    return _text((out or "up: ok").splitlines() +
                 ["note: verify with ts_status / ts_ping"])


def tool_down():
    ok, out, err = _ts(["down"], timeout=60)
    if not ok:
        hint = ((err or out).splitlines() +
                ["note: on Windows this may need an admin terminal / UAC;"])
        return _text(hint)
    return _text(out.splitlines() + ["note: down ok - the 100.x IPs are offline now"])


def tool_version():
    ok, out, err = _ts(["version"], timeout=30)
    return _text((out or err).splitlines()[:3])


TOOLS = {
    "ts_status": {
        "description": (
            "Tailscale state: installed/running, this device's name and "
            "100.x.x.x IPs, and all peers (name, IP, online, OS). The "
            "PC-Interconnect deploy loop workhorse: find the newly deployed "
            "peer's Tailscale IP here, then ts_ping it."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ts_ip": {
        "description": "This machine's Tailscale IPv4 address (100.x.x.x).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ts_ping": {
        "description": ("Ping a Tailscale peer once (IP or MagicDNS name) to "
                        "verify the encrypted tunnel works."),
        "inputSchema": {"type": "object", "properties": {
            "peer": {"type": "string",
                     "description": "100.x.x.x IP or MagicDNS hostname"}},
            "required": ["peer"]},
    },
    "ts_netcheck": {
        "description": ("Probe NAT type, UDP connectivity and DERP relay "
                        "latency - use when peers cannot connect directly "
                        "(China NAT / 打洞失败 diagnosis). Takes ~10-30s."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ts_up": {
        "description": ("Bring the Tailscale VPN up (STATE CHANGE). Optional "
                        "authkey for unattended login and/or hostname. On "
                        "Windows may need an admin terminal / UAC. Verify "
                        "afterwards with ts_status."),
        "inputSchema": {"type": "object", "properties": {
            "authkey": {"type": "string",
                        "description": "Tailscale auth key (optional)"},
            "hostname": {"type": "string",
                         "description": "hostname to register (optional)"}},
            "required": []},
    },
    "ts_down": {
        "description": ("Take the Tailscale VPN down (STATE CHANGE, 100.x IPs "
                        "go offline). On Windows may need admin / UAC."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ts_version": {
        "description": "Tailscale CLI version (also proves the CLI is installed).",
        "inputSchema": {"type": "object", "properties": {}},
    },
}

_DISPATCH = {
    "ts_status": lambda a: tool_status(),
    "ts_ip": lambda a: tool_ip(),
    "ts_ping": lambda a: tool_ping(a.get("peer")),
    "ts_netcheck": lambda a: tool_netcheck(),
    "ts_up": lambda a: tool_up(a.get("authkey"), a.get("hostname")),
    "ts_down": lambda a: tool_down(),
    "ts_version": lambda a: tool_version(),
}


def handle(req):
    rid = req.get("id")
    method = req.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "tailscale-mcp", "version": "1.0.0"}}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": n, "description": d["description"],
             "inputSchema": d["inputSchema"]} for n, d in TOOLS.items()]}}
    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        fn = _DISPATCH.get(name)
        if fn is None:
            return {"jsonrpc": "2.0", "id": rid, "error": {
                "code": -32601, "message": "unknown tool %s" % name}}
        try:
            result = {"content": fn(args)}
        except Exception as e:
            result = {"content": _text(
                "%s: %s" % (type(e).__name__, e)), "isError": True}
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {
            "code": -32601, "message": "method not found: %s" % method}}
    return None


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            resp = handle(json.loads(raw))
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "%s: %s" % (type(e).__name__, e)}}
        if resp:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
