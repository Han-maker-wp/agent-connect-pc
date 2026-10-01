#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP streamable-http 远程握手测试（对标 test_mcp_handshake.py 的角色，用于 HTTP 型 server）

用法:
  python tools/test_mcp_http_handshake.py http://127.0.0.1:8808/mcp
  python tools/test_mcp_http_handshake.py http://<目标机IP>:8808/mcp --auth-key <密钥>
  python tools/test_mcp_http_handshake.py http://127.0.0.1:8808/mcp --call DisplayInventory

流程: initialize -> notifications/initialized -> tools/list (-> tools/call)
仅用标准库；显式绕过系统代理（Clash 对局域网/Tailscale 链路不可靠）。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]


def make_opener():
    # 强制不走任何代理（Windows 下 urllib 会读注册表系统代理）
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(opener, url, payload, session=None, auth=None, timeout=30):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["mcp-session-id"] = session
    if auth:
        headers["Authorization"] = "Bearer " + auth
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with opener.open(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.status, resp.headers, body


def parse_body(body, content_type):
    """streamable-http 响应可能是 application/json 或 SSE(text/event-stream)。"""
    if "text/event-stream" in (content_type or ""):
        for line in body.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        continue
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def rpc(id_, method, params=None):
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="MCP endpoint, e.g. http://127.0.0.1:8808/mcp")
    ap.add_argument("--auth-key", default=None, help="Bearer 密钥（windows-mcp --auth-key）")
    ap.add_argument("--call", default=None, help="握手成功后试调用一个只读工具名")
    args = ap.parse_args()

    opener = make_opener()
    session = None
    server_info = {}
    used_proto = None

    # 1) initialize（逐个协议版本协商）
    for pv in PROTOCOL_VERSIONS:
        payload = rpc(1, "initialize", {
            "protocolVersion": pv,
            "capabilities": {},
            "clientInfo": {"name": "ap-interconnect-test", "version": "0.1.0"},
        })
        try:
            status, headers, body = post(opener, args.url, payload, auth=args.auth_key)
        except urllib.error.HTTPError as e:
            print(f"[FAIL] initialize HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
            sys.exit(1)
        except Exception as e:
            print(f"[FAIL] 连接失败 {args.url}: {e}")
            sys.exit(1)
        msg = parse_body(body, headers.get("content-type"))
        if msg and "result" in msg:
            session = headers.get("mcp-session-id")
            server_info = msg["result"].get("serverInfo", {})
            used_proto = msg["result"].get("protocolVersion", pv)
            break
        if msg and "error" in msg:
            print(f"[..] 协议 {pv} 被拒: {msg['error'].get('message', '')[:120]}，尝试下一版本")
    if not server_info:
        print("[FAIL] initialize 无有效响应（server 不兼容或路径不对）")
        sys.exit(1)
    print(f"[OK] initialize: server={server_info.get('name')} v{server_info.get('version')} "
          f"protocol={used_proto} session={session or '(无)'}")

    # 2) notifications/initialized
    try:
        status, _, _ = post(opener, args.url,
                            {"jsonrpc": "2.0", "method": "notifications/initialized"},
                            session=session, auth=args.auth_key)
        print(f"[OK] initialized 通知: HTTP {status}")
    except Exception as e:
        print(f"[WARN] initialized 通知异常（部分实现可省略）: {e}")

    # 3) tools/list
    try:
        status, headers, body = post(opener, args.url, rpc(2, "tools/list"),
                                     session=session, auth=args.auth_key)
    except Exception as e:
        print(f"[FAIL] tools/list: {e}")
        sys.exit(1)
    msg = parse_body(body, headers.get("content-type"))
    tools = (msg or {}).get("result", {}).get("tools", [])
    if not tools:
        print(f"[FAIL] tools/list 无工具: HTTP {status}, body 前 200 字符: {body[:200]}")
        sys.exit(1)
    names = [t.get("name") for t in tools]
    print(f"[OK] tools/list: {len(names)} 个工具 -> {', '.join(names)}")

    # 4) 可选 tools/call
    if args.call:
        try:
            status, headers, body = post(opener, args.url,
                                         rpc(3, "tools/call", {"name": args.call, "arguments": {}}),
                                         session=session, auth=args.auth_key)
            msg = parse_body(body, headers.get("content-type"))
            result = (msg or {}).get("result")
            if result is not None:
                text = json.dumps(result, ensure_ascii=False)
                print(f"[OK] tools/call {args.call}: HTTP {status}, 内容前 300 字符:\n{text[:300]}")
            else:
                print(f"[WARN] tools/call {args.call}: {str(msg)[:300]}")
        except Exception as e:
            print(f"[WARN] tools/call {args.call} 失败: {e}")

    print(f"\n[PASS] 全链路握手通过: {args.url}")


if __name__ == "__main__":
    main()
