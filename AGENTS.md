# AGENTS.md — PC InterConnect（AI agent 操作手册）

> 本文件写给 **AI agent** 阅读；人类用户请读 [README.md](README.md)（中文）/ [README.en.md](README.en.md)。
> 角色定义：**控制端** = 运行 agent 的电脑；**受控端 / 客户机** = 被操控的 Windows 电脑。
> 本项目的所有部署/运维流程都经过 2026-10-01 的真实跨网络部署实战校准。

## 一、项目心智模型（30 秒）

让控制端 agent 通过 MCP（streamable HTTP + Bearer 认证）操控另一台 Windows 电脑：截图、点击、键盘、文件、PowerShell 等 **20 个工具**。

- 受控端核心：`windows-mcp==0.8.7`（CursorTouch，PyPI，MIT），已由 PyInstaller 打包为**免依赖单文件 exe**
- 网络：Tailscale 组网——客户机用**控制端生成的 Single-use Auth Key** 加入控制端的 tailnet，**客户零注册/零邮箱**，跨网络 WireGuard 加密
- 与 android-mcp 的类比：ADB ↔ Tailscale+HTTP，ATX(uiautomator) ↔ windows-mcp(UIA)，14 工具 ↔ 20 工具
- 默认端口 8808；服务以 HKCU Run 启动项开机自启；受控端有一个最小化控制台窗口 = 服务本体，关掉即停止受控

## 二、关键文件地图

| 文件 | 角色 | 在哪台机运行 |
|---|---|---|
| `make_target_installer.bat` | 生成 `target-<昵称>/` 客户文件夹（密钥全内嵌） | 控制端 |
| `connect_target.bat` + `scripts/auto_connect_target.py` | 挂机等待客户装完，自动发现设备+自动验证连通 | 控制端 |
| `install_windows_mcp.bat` | 主安装脚本（离线 exe 优先 / 在线国内 CDN 兜底） | 受控端 |
| `install_on_target.bat` | **生成的一键安装器**（客户唯一要双击的文件） | 受控端 |
| `fix_tailscale.bat` / `fix_tailscale_template.bat` | Tailscale 自修复（winget → 官方 CDN MSI 降级链，密钥内嵌） | 受控端 / 模板 |
| `scripts/test_mcp_http_handshake.py` | 连通性验证（对任何 streamable-http MCP server 通用） | 控制端 |
| `scripts/test_mcp_stdio_bridge.py` | mcp-remote 桥接链路验证（stdio-only 客户端用） | 控制端 |
| `run_local_server.bat` | 本机回环测试实例（127.0.0.1:8808 免认证） | 控制端 |
| `uninstall_windows_mcp.bat` | 受控端彻底卸载（删启动项+防火墙规则） | 受控端 |
| `my-targets/<昵称>.env` | **密钥存档**（PORT/BEARER/TSKEY，gitignored，严禁外传/提交） | 控制端 |
| `target-<昵称>/` | 发给客户的文件夹（含密钥，gitignored，严禁提交） | — |

## 三、标准工作流 A：新客户接入（控制端 4 步 / 客户 2 步）

控制端依次执行：

1. **生成 Auth Key**：让用户在 https://login.tailscale.com/admin/settings/keys 生成 **Single-use** key（每个客户一个，用完即废）。agent 可以浏览器自动化代做：管理台 Keys 页 → Generate auth key → 勾选默认（Reusable=off）→ Generate → 点复制按钮 → 剪贴板读取并正则校验 `^tskey-auth-`。
2. **生成客户文件夹**：`make_target_installer.bat <昵称> <auth-key>`（昵称限 `[a-zA-Z0-9_-]`）。产出 `target-<昵称>/`（一键安装器 + 主脚本 + 离线 exe + fix_tailscale.bat，密钥全内嵌），密钥同时存档 `my-targets/<昵称>.env`。
3. **交付 + 挂机**：让用户把**整个文件夹**发给客户（微信/U盘），然后后台运行：
   `python scripts/auto_connect_target.py --name <昵称> --timeout 3600`
   （exit 0 = 连通；exit 2 = 超时，按输出提示排查；脚本会自动发现 tailnet 新设备并验证握手，PASS 时把客户 IP 追加进 env）
4. **接入 MCP 客户端**（每个客户一条独立条目，可多客户并行）：
   - stdio-only 客户端（ZCode 等）：mcp-remote 桥接 `http://<客户tailnet IP>:8808/mcp` + args 加 `--header "Authorization: Bearer <BEARER>"` + env `NO_PROXY` 加该 IP
   - 原生 HTTP 客户端（Claude Code/Cursor/OpenCode/Codex）：url + `Authorization` header 即可
   - 改任何 MCP 配置前先备份配置文件，改后新会话生效
5. **验收**：远程在客户桌面写测试文件并读回（见「远程操作要点」的 FileSystem 相对路径技巧），然后按用户要求登记设备。

客户侧话术（原样转告）：「解压后双击 `install_on_target.bat`，管理员提示点『是』（最多两次），看到完成面板后黑窗口保持开着，别的什么都不用做。若中途失败，双击 `fix_tailscale.bat` 再试一次，仍失败就截图发回来。」

## 四、标准工作流 B：已初始化客户（日常 / 断线恢复）

1. `tailscale status` 确认客户机在线——显示 `offline / last seen` = 客户关机/合盖睡眠/断网，**这不是服务故障**，让客户开机联网即可
2. 验证：`python scripts/test_mcp_http_handshake.py http://<客户IP>:8808/mcp --auth-key <my-targets/<昵称>.env 里的 BEARER>`
3. 正常操控。客户日常**零操作**（服务开机自启）；停止受控 = 关黑窗口，或受控端跑 `uninstall_windows_mcp.bat`

## 五、故障排查决策树（按序判别）

1. `tailscale status` **看不到**客户机 → Tailscale 未装好/未入网 → 客户双击文件夹里的 `fix_tailscale.bat`（自带 winget→CDN MSI 降级链）
2. 看得到，但 `tailscale ping <IP>` 不通 → 客户机离线（睡眠/关机）→ 等上线，不是服务问题
3. ping 通，但 TCP 8808 超时 → 客户机防火墙缺规则 → 客户机管理员执行：
   `netsh advfirewall firewall add rule name="windows-mcp-8808" dir=in action=allow protocol=TCP localport=8808`
4. 控制端连不上 100.x（能 ping 通）→ Clash 等系统代理截流 → 在 MCP 客户端条目的 env `NO_PROXY` 加客户 IP（**不要改系统代理变量**）
5. 握手 401 → BEARER 不匹配 → 核对 `my-targets/<昵称>.env`
6. 密钥疑似泄露 → 管理台吊销 Auth Key（单次的本来就即焚）+ **轮换 BEARER**：
   生成新 key → 远程改客户机 HKCU Run 启动项（新 key）→ 重启受控服务 → 新 key 验证 PASS/旧 key 验证 401 → 同步更新 `my-targets/*.env` 和所有 MCP 客户端配置。轮换操作注意下文「远程操作要点」的自杀式 taskkill 问题。

## 六、远程操作要点（经 MCP 操控客户机时）

- `FileSystem` 工具的**相对路径 = 客户的 Desktop**（写桌面文件直接 `path: "xxx.txt"`）
- `PowerShell` 工具的文本输出带 `Response: ... / Status Code: N` 包装，解析时用 startswith/endswith/子串查找——**不要写含反斜杠的正则**（转义在传输链路会减半出错，血泪教训）
- 需要**重启客户机上的受控服务**（如轮换密钥）时：先 `FileSystem` 写一个延迟 4 秒的临时 .cmd（reg add 新 Run key → taskkill → start），再用 PowerShell 分离执行（`Start-Process cmd -ArgumentList '/c', ... -WindowStyle Hidden`）——直接在当前会话 taskkill 会杀死自己脚下的 MCP 连接
- 文件内容含引号/反斜杠时优先用 `FileSystem` 写脚本文件再执行，避免多层引号转义

## 七、安全红线（必须遵守，违反即事故）

1. 只在获得设备主人**明确同意**的电脑上部署；操作范围事先说清；客户随时可停（关黑窗口 / `uninstall_windows_mcp.bat`）
2. **永远禁止**支付/转账类操作；删除类操作先问设备主人；更改系统设置前记录原值
3. 屏幕截图属敏感数据，不得外传
4. **严禁把含密钥的文件提交进仓库**：`my-targets/`、`target-*/`、`*.zip` 已 gitignore；`git add` 前确认；一旦误提交：`git rm --cached` + `--amend` + `--force-with-lease` 抹除，并轮换 BEARER（单次 Auth Key 消耗后即无害）
5. Auth Key 一律 Single-use；不再使用的设备在管理台一键移除；不再使用的客户跑 uninstall

## 八、改本仓库代码的工程铁律（实战教训，逐条都踩过）

1. **所有 .bat 必须纯 ASCII + CRLF**：cmd 按 GBK 解析批处理，UTF-8 中文会把脚本炸碎；带 goto/标签的 LF 文件有解析风险。每次改完逐字节校验（无 >127 字节 + CRLF 行数正确）；`.gitattributes` 已锁 `*.bat -text`（保证 raw 下载即 CRLF）
2. `schtasks /Create /SC ONLOGON` **必须管理员**（实测 Access is denied）→ 自启用 HKCU Run 启动项（`reg add`，值 = 完整命令行，`\` 转义写法 `\"...\"`）
3. `windows-mcp install` 子命令不支持 `--auth-key`；`serve` 绑定非回环地址无认证会拒绝启动（好默认，不要用 `--allow-insecure-remote` 绕过）
4. PyInstaller 打包 windows-mcp：必须 `--exclude-module mcp.cli`（否则 mcp.cli 导入即 SystemExit(1)）；运行用 `python -m windows_mcp`（pip 生成的 Scripts exe 启动器内嵌绝对路径，不可搬迁）
5. winget 包 ID **大小写敏感**：`Tailscale.Tailscale`
6. 在线安装链路必须全程国内 CDN（npmmirror 的 python-build-standalone 镜像 + 清华 PyPI，ghproxy/GitHub 仅作回退）——目标机可能完全没有代理
7. Python `subprocess` 调 npm 等 `.cmd` 程序：先 `shutil.which` 拿全路径再调用
8. Git Bash 执行 Windows 命令：加 `MSYS_NO_PATHCONV=1`（防 `/Create` 被转成文件路径）；解压 tar 用系统自带 `%SYSTEMROOT%\System32\tar.exe`（Git Bash 的 GNU tar 会把 `C:` 当远程主机名）
9. ZCode 的 MCP 配置在 `~/.zcode/cli/config.json` 的 `mcp.servers`（改前备份）；未确认支持原生 `type:http`，用 mcp-remote 桥接最稳
10. 浏览器自动化（windows-mcp 的 Snapshot）对多标签 Edge 的 UI 树提取会超时 → 用 `use_vision` 纯视觉截图（返回 artifact png 再读）+ 坐标点击；Tailscale 管理台生成 Auth Key 的全流程可由此自动化
