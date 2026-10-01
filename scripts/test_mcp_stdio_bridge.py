#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stdio bridge test: verify the exact chain many MCP clients use to reach a
remote HTTP MCP server:

    client (stdio) -> mcp-remote (npm pkg) -> streamable HTTP MCP server

Auto-detects node and the globally installed mcp-remote package.
Prerequisite for the bridge: npm install -g mcp-remote

Usage:
  python test_mcp_stdio_bridge.py [url]
  python test_mcp_stdio_bridge.py http://192.168.1.20:8808/mcp --auth-key KEY
  python test_mcp_stdio_bridge.py --node /path/to/node --proxy /path/to/proxy.js URL
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time


def find_node(explicit=None):
    if explicit:
        return explicit
    return shutil.which("node")


def find_proxy(explicit=None):
    """Locate mcp-remote/dist/proxy.js. Returns (path_or_None, tried_list)."""
    tried = []
    if explicit:
        return (explicit if os.path.isfile(explicit) else None), [explicit]

    npm_paths = [p for p in (shutil.which("npm"), shutil.which("npm.cmd"),
                             shutil.which("npm.exe")) if p]
    for npm in npm_paths:
        try:
            root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True,
                                  timeout=20).stdout.strip()
            tried.append(os.path.join(root, "mcp-remote", "dist", "proxy.js"))
            if root and os.path.isfile(tried[-1]):
                return tried[-1], tried
        except Exception:
            continue

    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
    for c in [
        os.path.join(appdata, "npm", "node_modules", "mcp-remote", "dist", "proxy.js"),
        os.path.join(home, ".npm-global", "lib", "node_modules", "mcp-remote", "dist", "proxy.js"),
        "/usr/local/lib/node_modules/mcp-remote/dist/proxy.js",
    ]:
        tried.append(c)
        if os.path.isfile(c):
            return c, tried
    return None, tried


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default="http://127.0.0.1:8808/mcp")
    ap.add_argument("--auth-key", default=None, help="Bearer key, passed to mcp-remote via --header")
    ap.add_argument("--node", default=None, help="path to node executable")
    ap.add_argument("--proxy", default=None, help="path to mcp-remote/dist/proxy.js")
    args = ap.parse_args()

    node = find_node(args.node)
    if not node:
        print("[FAIL] node not found in PATH. Install Node.js or pass --node.")
        sys.exit(1)
    proxy, tried = find_proxy(args.proxy)
    if not proxy:
        print("[FAIL] mcp-remote not found. Install it globally: npm install -g mcp-remote")
        print("  (or pass --proxy /path/to/mcp-remote/dist/proxy.js)")
        print("  Paths tried:")
        for t in tried:
            print("   -", t)
        sys.exit(1)

    cmd = [node, proxy, args.url]
    if args.auth_key:
        cmd += ["--header", "Authorization: Bearer " + args.auth_key]
    print(f"[..] bridge: {' '.join(cmd)}")

    env = dict(os.environ)
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    env["no_proxy"] = "localhost,127.0.0.1,::1"
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", env=env)

    out_lines, err_lines = [], []
    got_tools = threading.Event()

    def drain(stream, sink):
        for line in stream:
            sink.append(line.rstrip())
            try:
                msg = json_loads(line)
                if msg and msg.get("id") == 2:
                    got_tools.set()
            except Exception:
                pass

    threading.Thread(target=drain, args=(p.stdout, out_lines), daemon=True).start()
    threading.Thread(target=drain, args=(p.stderr, err_lines), daemon=True).start()

    def send(obj):
        p.stdin.write(json_dumps(obj) + "\n")
        p.stdin.flush()

    def json_dumps(o):
        import json
        return json.dumps(o)

    def json_loads(s):
        import json
        return json.loads(s)

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                     "clientInfo": {"name": "bridge-test", "version": "0.1"}}})
    time.sleep(4)  # mcp-remote cold start + first connect
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    if not got_tools.wait(45):
        print("[FAIL] no tools/list response within 45s")
        print("--- stderr tail ---")
        for l in err_lines[-15:]:
            print(l)
        p.kill()
        sys.exit(1)

    server_info, tool_names = None, []
    for line in out_lines:
        try:
            msg = json_loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("id") == 1 and "result" in msg:
            server_info = msg["result"].get("serverInfo", {})
        if msg.get("id") == 2 and "result" in msg:
            tool_names = [t.get("name") for t in msg["result"].get("tools", [])]

    p.terminate()
    if server_info and tool_names:
        print(f"[OK] via mcp-remote bridge: server={server_info.get('name')} v{server_info.get('version')}")
        print(f"[OK] tools/list: {len(tool_names)} tools -> {', '.join(tool_names)}")
        print(f"\n[PASS] client bridge chain works: stdio -> mcp-remote -> {args.url}")
    else:
        print("[FAIL] incomplete bridge response")
        print("--- stdout tail ---")
        for l in out_lines[-10:]:
            print(l)
        sys.exit(1)


if __name__ == "__main__":
    main()
