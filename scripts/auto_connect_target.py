#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_connect_target.py — 控制端一键等待并连接新目标机（配合 make_target_installer.bat）

原理（三行信息全自动，对方零抄写）：
  PORT/KEY 已由 make_target_installer 内嵌到对方安装器并存在 my-targets/<昵称>.env；
  对方用你的 Auth Key 加入你的 tailnet，新设备会出现在 `tailscale status` 里，
  本脚本轮询发现后自动验证连通，打印可粘贴的 MCP 配置。

用法:
  python scripts/auto_connect_target.py --name <昵称>
  python scripts/auto_connect_target.py --name <昵称> --ip 100.x.y.z   # 跳过发现
  python scripts/auto_connect_target.py --name <昵称> --timeout 1800
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS_CANDIDATES = [r"C:\Program Files\Tailscale\tailscale.exe"]


def ts_exe():
    for c in TS_CANDIDATES:
        if os.path.isfile(c):
            return c
    p = shutil.which("tailscale")
    if p:
        return p
    print("[FAIL] 找不到 tailscale CLI —— 控制端先安装 Tailscale 并登录")
    sys.exit(1)


def load_env(name):
    path = os.path.join(ROOT, "my-targets", name + ".env")
    if not os.path.isfile(path):
        print(f"[FAIL] 未找到 {path}")
        print("       先运行 make_target_installer.bat <昵称> <auth-key> 生成")
        sys.exit(1)
    cfg = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def ts_peers(ts):
    """返回 {hostname: {ip, dns, online}}，不含本机（Self）。"""
    try:
        r = subprocess.run([ts, "status", "--json"], capture_output=True,
                           text=True, timeout=20)
        data = json.loads(r.stdout or "{}")
    except Exception as e:
        print(f"    (tailscale status 读取失败: {e})")
        return {}
    peers = {}
    for pid, p in (data.get("Peer") or {}).items():
        name = (p.get("HostName") or p.get("DNSName") or pid).strip()
        ips = p.get("TailscaleIPs") or []
        peers[name] = {"ip": ips[0] if ips else None,
                       "online": bool(p.get("Online", False))}
    return peers


def self_ip(ts):
    try:
        r = subprocess.run([ts, "ip", "-4"], capture_output=True, text=True, timeout=15)
        return r.stdout.strip().splitlines()[0].strip()
    except Exception:
        return None


def probe(ip, port, key, timeout=8):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "auto-connect", "version": "0.1"}}}).encode()
    req = urllib.request.Request(
        f"http://{ip}:{port}/mcp", data=body,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": "Bearer " + key},
        method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print("    -> HTTP 401（密钥不匹配？确认用的是同一份 my-targets 配置）")
        return False
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="make_target_installer 时的昵称")
    ap.add_argument("--ip", default=None, help="跳过设备发现，直接验证该 IP")
    ap.add_argument("--port", type=int, default=None, help="覆盖 .env 里的端口")
    ap.add_argument("--timeout", type=int, default=1800, help="等待秒数（默认 1800）")
    args = ap.parse_args()

    cfg = load_env(args.name)
    port = args.port or int(cfg.get("PORT", "8808"))
    key = cfg.get("BEARER", "")
    if not key:
        print("[FAIL] my-targets 配置里没有 BEARER")
        sys.exit(1)

    ts = ts_exe()
    me = self_ip(ts)
    base = set(ts_peers(ts).keys())
    print(f"[..] 控制端 tailnet IP: {me}；已知设备 {len(base)} 台")
    print(f"[..] 等待目标机上线并完成安装（最长 {args.timeout}s，每 10s 轮询）...")
    print("     （对方装完的瞬间这里会自动发现并验证，本窗口保持开着即可）")

    deadline = time.time() + args.timeout
    tried = {}
    while time.time() < deadline:
        peers = ts_peers(ts)
        # 候选：新出现的设备优先；没有新设备则探测所有在线设备（Bearer 不对就是 401，无害）
        fresh = {n: p for n, p in peers.items() if n not in base}
        pool = fresh or {n: p for n, p in peers.items()
                         if p["ip"] and p["ip"] != me and p.get("online", True)}
        for name, p in pool.items():
            ip = args.ip or p.get("ip")
            if not ip or tried.get(ip, 0) and time.time() - tried[ip] < 30:
                continue
            tried[ip] = time.time()
            tag = "（新设备!）" if name in fresh else ""
            print(f"[..] 探测 tailnet 设备 {name} {ip}:{port} {tag}")
            if probe(ip, port, key):
                print(f"\n[PASS] 已连通: {name} {ip}:{port}")
                env_path = os.path.join(ROOT, "my-targets", args.name + ".env")
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write(f"TARGET_HOSTNAME={name}\nTARGET_IP={ip}\n")
                print("=" * 60)
                print("把 ZCode（或其他 agent）的 pc-interconnect 指到这台机器:")
                print(f'  URL : http://{ip}:{port}/mcp')
                print(f'  认证: Authorization: Bearer <my-targets/{args.name}.env 里的 BEARER>')
                print("ZCode mcp-remote 桥接 args 示例:")
                print(f'  ["<npm全局>/mcp-remote/dist/proxy.js", "http://{ip}:{port}/mcp",')
                print(f'   "--header", "Authorization: Bearer {key[:8]}...（完整值在 env 文件）"]')
                print("=" * 60)
                sys.exit(0)
        print("    ... 等待中（对方可能还在下载/安装；若对方 UAC 点了拒绝会一直不通）")
        time.sleep(10)

    print(f"\n[TIMEOUT] {args.timeout}s 内未等到可连通的目标机。排查：")
    print("  1) 对方是否双击了 install_on_target.bat 并点完管理员提示？")
    print("  2) 对方 Tailscale 是否已登录（本机出现新设备）？tailscale status 看一眼")
    print("  3) 防火墙规则是否加上（UAC 被拒绝就不会通）")
    sys.exit(2)


if __name__ == "__main__":
    main()
