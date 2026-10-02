"""Shared controller-side operations for AgentConnect-PC.

The module deliberately uses only the Python standard library.  It is the
single source of truth used by both the CLI and the Tkinter GUI.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


APP_NAME = "AgentConnect-PC"
APP_VERSION = "1.0.0"
DEFAULT_PORT = 8808
DEFAULT_TIMEOUT = 1800
TS_API = "https://api.tailscale.com/api/v2/tailnet/-/keys"


class AgentConnectError(RuntimeError):
    """A user-facing controller error."""


@dataclass
class TargetConfig:
    name: str
    path: Path
    port: int = DEFAULT_PORT
    bearer: str = ""
    tskey: str = ""
    target_ip: str = ""
    target_hostname: str = ""
    created: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.bearer and self.port)


@dataclass
class Peer:
    hostname: str
    ip: str
    online: bool
    os: str = ""
    dns_name: str = ""


@dataclass
class ProbeResult:
    ok: bool
    status: str
    detail: str = ""


@dataclass
class ConnectionResult:
    ok: bool
    target: Optional[TargetConfig] = None
    peer: Optional[Peer] = None
    detail: str = ""


LogFn = Callable[[str], None]


def project_root() -> Path:
    """Return the data/template directory for source and frozen builds."""
    override = os.environ.get("AGENTCONNECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def targets_dir(root: Optional[Path] = None) -> Path:
    return (root or project_root()) / "my-targets"


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_target(name: str, root: Optional[Path] = None) -> TargetConfig:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise AgentConnectError("目标昵称只能包含字母、数字、下划线和连字符")
    path = targets_dir(root) / f"{name}.env"
    if not path.is_file():
        raise AgentConnectError(f"未找到目标配置：{path}")
    values = _parse_env(path)
    try:
        port = int(values.get("PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise AgentConnectError(f"目标配置端口无效：{path}") from exc
    return TargetConfig(
        name=name,
        path=path,
        port=port,
        bearer=values.get("BEARER", ""),
        tskey=values.get("TSKEY", ""),
        target_ip=values.get("TARGET_IP", ""),
        target_hostname=values.get("TARGET_HOSTNAME", ""),
        created=values.get("CREATED", ""),
    )


def list_targets(root: Optional[Path] = None) -> list[TargetConfig]:
    directory = targets_dir(root)
    if not directory.is_dir():
        return []
    result: list[TargetConfig] = []
    for path in sorted(directory.glob("*.env")):
        if path.name == "tailscale-api.env":
            continue
        try:
            result.append(load_target(path.stem, root))
        except AgentConnectError:
            continue
    return result


def tailscale_executable() -> Optional[str]:
    candidates = [
        shutil.which("tailscale"),
        r"C:\Program Files\Tailscale\tailscale.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def run_tailscale(args: list[str], timeout: int = 45) -> tuple[bool, str, str]:
    executable = tailscale_executable()
    if not executable:
        raise AgentConnectError(
            "找不到 Tailscale CLI。请安装 Tailscale 并登录后重试："
            " https://tailscale.com/download/windows"
        )
    try:
        completed = subprocess.run(
            [executable, *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentConnectError(f"Tailscale 命令超时：tailscale {' '.join(args)}") from exc
    output = completed.stdout.strip()
    error = completed.stderr.strip()
    return completed.returncode == 0, output, error


def tailscale_version() -> str:
    ok, output, error = run_tailscale(["version"], 30)
    if not ok:
        raise AgentConnectError(error or output or "Tailscale version 失败")
    return (output or error).splitlines()[0]


def tailscale_status() -> tuple[dict, list[Peer]]:
    ok, output, error = run_tailscale(["status", "--json"], 120)
    if not ok:
        raise AgentConnectError(error or output or "Tailscale status 失败")
    try:
        data = json.loads(output or "{}")
    except json.JSONDecodeError as exc:
        raise AgentConnectError(f"Tailscale status 返回了非 JSON：{output[:300]}") from exc
    peers: list[Peer] = []
    for peer in (data.get("Peer") or {}).values():
        ips = peer.get("TailscaleIPs") or []
        peers.append(Peer(
            hostname=(peer.get("HostName") or peer.get("DNSName") or "unknown").strip(),
            ip=ips[0] if ips else "",
            online=bool(peer.get("Online", False)),
            os=peer.get("OS", ""),
            dns_name=peer.get("DNSName", ""),
        ))
    return data, peers


def local_tailscale_ip() -> str:
    ok, output, error = run_tailscale(["ip", "-4"], 30)
    if not ok:
        raise AgentConnectError(error or output or "无法读取 Tailscale IPv4")
    return next((line.strip() for line in output.splitlines() if line.strip()), "")


def ping_peer(peer: str) -> str:
    if not peer.strip():
        raise AgentConnectError("请提供 Tailscale IP 或 MagicDNS 名称")
    ok, output, error = run_tailscale(["ping", "-c", "1", peer.strip()], 60)
    text = "\n".join(part for part in (output, error) if part).strip()
    if not ok:
        raise AgentConnectError(text or f"无法连接 {peer}")
    return text or f"已连通：{peer}"


def netcheck() -> str:
    ok, output, error = run_tailscale(["netcheck"], 120)
    text = "\n".join(part for part in (output, error) if part).strip()
    if not ok:
        raise AgentConnectError(text or "Tailscale netcheck 失败")
    return text


def probe_mcp(ip: str, port: int, bearer: str, timeout: int = 8) -> ProbeResult:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": APP_NAME, "version": APP_VERSION},
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        f"http://{ip}:{port}/mcp", data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + bearer,
        }, method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status == 200:
                return ProbeResult(True, "MCP OK", "initialize 返回 HTTP 200")
            return ProbeResult(False, f"HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return ProbeResult(False, f"HTTP {exc.code}", "Bearer 密钥不匹配")
        return ProbeResult(False, f"HTTP {exc.code}")
    except Exception as exc:
        return ProbeResult(False, "连接失败", str(exc))


def discover_and_connect(target: TargetConfig, timeout: int = DEFAULT_TIMEOUT,
                         log: Optional[LogFn] = None,
                         preferred_ip: Optional[str] = None) -> ConnectionResult:
    log = log or (lambda _message: None)
    if not target.bearer:
        return ConnectionResult(False, target, detail="目标配置缺少 BEARER")
    status, peers = tailscale_status()
    self_data = status.get("Self") or {}
    own_ips = set(self_data.get("TailscaleIPs") or [])
    baseline = {peer.hostname for peer in peers}
    log(f"控制端在线；当前已发现 {len(peers)} 台 tailnet 设备")
    deadline = time.time() + max(1, timeout)
    tried: dict[str, float] = {}
    while time.time() < deadline:
        _, peers = tailscale_status()
        fresh = [peer for peer in peers if peer.hostname not in baseline]
        candidates = fresh or [peer for peer in peers if peer.online]
        for peer in candidates:
            ip = preferred_ip or peer.ip
            if not ip or ip in own_ips:
                continue
            if ip in tried and time.time() - tried[ip] < 20:
                continue
            tried[ip] = time.time()
            log(f"验证 {peer.hostname} ({ip}:{target.port})")
            result = probe_mcp(ip, target.port, target.bearer)
            if result.ok:
                target.target_ip = ip
                target.target_hostname = peer.hostname
                append_target_metadata(target)
                return ConnectionResult(True, target, peer, "Tailscale + MCP 已连通")
            log(f"  {result.status}: {result.detail}".strip())
        remaining = max(0, int(deadline - time.time()))
        log(f"等待目标机上线；剩余约 {remaining}s")
        time.sleep(10)
    return ConnectionResult(False, target, detail="超时：未发现可用的目标机 MCP 服务")


def append_target_metadata(target: TargetConfig) -> None:
    existing = _parse_env(target.path)
    existing["TARGET_IP"] = target.target_ip
    existing["TARGET_HOSTNAME"] = target.target_hostname
    lines = [f"{key}={value}" for key, value in existing.items()]
    target.path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_management_token(root: Optional[Path] = None) -> str:
    values = _parse_env(targets_dir(root) / "tailscale-api.env")
    token = values.get("TSMGMT_TOKEN", "")
    if not token:
        raise AgentConnectError(
            "未找到 TSMGMT_TOKEN。请将 Tailscale 管理 token 存入 "
            "my-targets/tailscale-api.env"
        )
    return token


def generate_auth_key(name: str, expiry_days: int = 90,
                      root: Optional[Path] = None) -> str:
    token = _load_management_token(root)
    payload = json.dumps({
        "description": f"{APP_NAME} {name}",
        "expirySeconds": expiry_days * 86400,
        "capabilities": {"devices": {"create": {"reusable": False, "ephemeral": False}}},
    }).encode("utf-8")
    request = urllib.request.Request(
        TS_API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        hint = "管理 token 过期或无效，请更新 my-targets/tailscale-api.env" if exc.code in (401, 403) else ""
        raise AgentConnectError(f"Tailscale API {exc.code}: {detail} {hint}".strip()) from exc
    key = data.get("key")
    if not key:
        raise AgentConnectError("Tailscale API 没有返回 Auth Key")
    return key


def _safe_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise AgentConnectError("昵称只能包含字母、数字、下划线和连字符")
    return name


def _replace_text(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\r\n" if path.suffix.lower() == ".bat" else "\n")


def create_target_bundle(name: str, auth_key: str, root: Optional[Path] = None,
                         source_dir: Optional[Path] = None) -> tuple[Path, TargetConfig]:
    root = root or project_root()
    source_dir = source_dir or project_root()
    name = _safe_name(name)
    if not auth_key.startswith("tskey-auth-"):
        raise AgentConnectError("Auth Key 格式不对，应以 tskey-auth- 开头")
    port = DEFAULT_PORT
    bearer = secrets.token_urlsafe(24)
    output = root / f"target-{name}"
    output.mkdir(parents=True, exist_ok=True)
    (targets_dir(root)).mkdir(parents=True, exist_ok=True)
    installer = source_dir / "install_windows_mcp.bat"
    exe_candidates = [
        source_dir / "windows-mcp-server.exe",
        source_dir / "dist" / "windows-mcp-server.exe",
        source_dir / "release-assets" / "windows-mcp-server.exe",
    ]
    if not installer.is_file():
        raise AgentConnectError(f"找不到受控端安装脚本：{installer}")
    shutil.copy2(installer, output / installer.name)
    exe = next((candidate for candidate in exe_candidates if candidate.is_file()), None)
    if exe:
        shutil.copy2(exe, output / exe.name)
    else:
        raise AgentConnectError(
            "找不到 windows-mcp-server.exe。请先下载 GitHub Release 资产，"
            "放在项目根目录或 release-assets/ 后再生成目标包。"
        )
    target_install = output / "install_on_target.bat"
    target_install.write_text(
        "@echo off\r\n"
        "rem Generated by AgentConnect-PC. Do not edit the baked credentials.\r\n"
        f'call "%~dp0install_windows_mcp.bat" {port} {bearer} {auth_key}\r\n',
        encoding="ascii", newline="",
    )
    template = source_dir / "fix_tailscale_template.bat"
    if template.is_file():
        (output / "fix_tailscale.bat").write_text(
            template.read_text(encoding="utf-8").replace("__TSKEY__", auth_key),
            encoding="ascii", newline="",
        )
    env_path = targets_dir(root) / f"{name}.env"
    env_path.write_text(
        f"PORT={port}\nBEARER={bearer}\nTSKEY={auth_key}\nCREATED={time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        encoding="utf-8",
    )
    return output, TargetConfig(name=name, path=env_path, port=port, bearer=bearer, tskey=auth_key)


def config_snippets(target: TargetConfig) -> dict[str, str]:
    if not target.target_ip:
        raise AgentConnectError("目标尚未连通，缺少 TARGET_IP")
    url = f"http://{target.target_ip}:{target.port}/mcp"
    header = f"Authorization: Bearer {target.bearer}"
    return {
        "claude": f'claude mcp add --transport http agent-connect-{target.name} {url} --header "{header}"',
        "cursor": json.dumps({"mcpServers": {f"agent-connect-{target.name}": {
            "url": url, "headers": {"Authorization": f"Bearer {target.bearer}"}}}}, ensure_ascii=False, indent=2),
        "opencode": json.dumps({"mcp": {f"agent-connect-{target.name}": {
            "type": "remote", "url": url,
            "headers": {"Authorization": f"Bearer {target.bearer}"}}}}, ensure_ascii=False, indent=2),
        "zcode": json.dumps({"type": "stdio", "command": "node", "args": [
            "<npm-global>/mcp-remote/dist/proxy.js", url,
            "--header", header], "env": {"NO_PROXY": target.target_ip}}, ensure_ascii=False, indent=2),
        "codex": f"[mcp_servers.agent-connect-{target.name}]\nurl = \"{url}\"",
    }
