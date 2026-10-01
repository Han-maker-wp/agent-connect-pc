#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tailscale_new_authkey.py — 用 Tailscale API 自动生成单次 Auth Key（免开管理台）

前提（一次性，约 2 分钟）：
  控制台 https://login.tailscale.com/admin/settings/keys -> "Generate access token..."
  （默认 90 天有效）-> 复制 token 存入 my-targets/tailscale-api.env：
    TSMGMT_TOKEN=tskey-api-xxxxx
  到期后重新生成替换即可（本脚本会给出明确报错）。

用法:
  python scripts/tailscale_new_authkey.py --name <昵称>
  成功时最后一行就是新 Auth Key（单次使用，供 make_target_installer 内嵌）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, "my-targets", "tailscale-api.env")
API = "https://api.tailscale.com/api/v2/tailnet/-/keys"


def load_token():
    if not os.path.isfile(ENV_PATH):
        print(f"[FAIL] 未找到 {ENV_PATH}", file=sys.stderr)
        print("一次性配置（约 2 分钟）:", file=sys.stderr)
        print("  1. 打开 https://login.tailscale.com/admin/settings/keys", file=sys.stderr)
        print('  2. 点 "Generate access token..."（默认 90 天）', file=sys.stderr)
        print("  3. 复制 token 存入上述文件: TSMGMT_TOKEN=tskey-api-xxxxx", file=sys.stderr)
        sys.exit(1)
    for line in open(ENV_PATH, encoding="utf-8"):
        line = line.strip()
        if line.startswith("TSMGMT_TOKEN="):
            return line.split("=", 1)[1].strip()
    print("[FAIL] env 文件里没有 TSMGMT_TOKEN", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="客户昵称（写进 key 描述）")
    ap.add_argument("--expiry-days", type=int, default=90, help="Auth Key 有效期天数（默认 90）")
    args = ap.parse_args()
    token = load_token()

    body = json.dumps({
        "description": "pc-interconnect " + args.name,
        "expirySeconds": args.expiry_days * 86400,
        "capabilities": {
            "devices": {
                "create": {
                    "reusable": False,   # 单次使用：装完即废，泄露无忧
                    "ephemeral": False,  # 设备长期保留在 tailnet
                }
            }
        },
    }).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token}, method="POST")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        print(f"[FAIL] API {e.code}: {detail}", file=sys.stderr)
        if e.code in (401, 403):
            print("token 过期或无效——去管理台重新生成 access token 并更新 my-targets/tailscale-api.env",
                  file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Auth Key 已生成 (id={data.get('id')}, 单次, {args.expiry_days} 天, "
          f"描述: pc-interconnect {args.name})", file=sys.stderr)
    print(data["key"])  # stdout 最后一行 = key（纯 ASCII，供 bat 的 for /f 捕获）


if __name__ == "__main__":
    main()
