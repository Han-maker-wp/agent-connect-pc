"""AgentConnect-PC command-line controller."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import (
    AgentConnectError, APP_NAME, DEFAULT_TIMEOUT, config_snippets,
    create_target_bundle, discover_and_connect, generate_auth_key,
    list_targets, load_target, local_tailscale_ip, netcheck,
    ping_peer, tailscale_status, tailscale_version,
)


def _root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None,
                        help="项目数据目录（默认：程序所在项目目录）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-connect",
        description="AgentConnect-PC：为 AI Agent 管理远程 Windows PC 的 Tailscale + MCP 控制端。",
        epilog="如果不确定怎么用，可以把本项目交给你的 AI Agent，让它先阅读 AGENTS.md。",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="显示 Tailscale 自身状态和 peers")
    _root_arg(status)
    status.add_argument("--json", action="store_true", dest="as_json")

    sub.add_parser("version", help="显示 Tailscale CLI 版本")
    ip = sub.add_parser("ip", help="显示控制端 Tailscale IPv4")
    ip.add_argument("--root", type=Path, default=None)
    ping = sub.add_parser("ping", help="验证 Tailscale peer 连通性")
    ping.add_argument("peer")
    net = sub.add_parser("netcheck", help="诊断 NAT、UDP 和 DERP")
    net.add_argument("--root", type=Path, default=None)

    new = sub.add_parser("new", help="生成目标机文件夹和密钥存档")
    new.add_argument("name", help="目标昵称：字母/数字/_/-")
    new.add_argument("--auth-key", help="已有 Tailscale single-use Auth Key")
    new.add_argument("--expiry-days", type=int, default=90)
    _root_arg(new)

    wait = sub.add_parser("wait", help="等待目标机加入 tailnet 并验证 MCP")
    wait.add_argument("name")
    wait.add_argument("--ip", default=None)
    wait.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    _root_arg(wait)

    snippets = sub.add_parser("snippets", help="输出各 AI 客户端的 MCP 配置")
    snippets.add_argument("name")
    snippets.add_argument("--client", choices=["all", "claude", "cursor", "opencode", "zcode", "codex"], default="all")
    _root_arg(snippets)
    return parser


def _print_status(as_json: bool) -> int:
    data, peers = tailscale_status()
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    self_data = data.get("Self") or {}
    print(f"Tailscale: {data.get('BackendState', 'unknown')}")
    print(f"本机: {self_data.get('HostName', '')}  {', '.join(self_data.get('TailscaleIPs') or [])}")
    if not peers:
        print("Peers: (none)")
    for peer in peers:
        print(f"- {'online' if peer.online else 'offline':7} {peer.hostname:28} {peer.ip:16} {peer.os}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            return _print_status(args.as_json)
        if args.command == "version":
            print(tailscale_version())
            return 0
        if args.command == "ip":
            print(local_tailscale_ip())
            return 0
        if args.command == "ping":
            print(ping_peer(args.peer))
            return 0
        if args.command == "netcheck":
            print(netcheck())
            return 0
        if args.command == "new":
            auth = args.auth_key or generate_auth_key(args.name, args.expiry_days, args.root)
            output, target = create_target_bundle(args.name, auth, args.root)
            print(f"已生成：{output}")
            print(f"密钥存档：{target.path}")
            print(f"下一步：把整个文件夹发给受控端，再运行 agent-connect wait {args.name}")
            return 0
        if args.command == "wait":
            target = load_target(args.name, args.root)
            result = discover_and_connect(target, args.timeout, print, args.ip)
            if not result.ok:
                print(f"[FAIL] {result.detail}", file=sys.stderr)
                return 2
            print(f"[PASS] {result.detail}: {target.target_ip}:{target.port}")
            return 0
        if args.command == "snippets":
            snippets = config_snippets(load_target(args.name, args.root))
            selected = snippets if args.client == "all" else {args.client: snippets[args.client]}
            for client, text in selected.items():
                print(f"\n--- {client} ---\n{text}")
            return 0
    except AgentConnectError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
