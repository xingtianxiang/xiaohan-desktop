# 小汉 Mac 构建工程

状态：M 系列与 Intel 两个 Mac 包均已完成云端构建和自动化验收。此目录是源码工程；可直接分享的应用包位于上一级 `小汉-macOS-arm64.zip` 和 `小汉-macOS-x86_64.zip`。

私有仓库：https://github.com/xingtianxiang/xiaohan-desktop 。成功运行：https://github.com/xingtianxiang/xiaohan-desktop/actions/runs/43402795962 ，构建提交 `a4c9613bb2928bdeca9f7506969c9a25bf94c7be`。每种架构 52 项单元测试通过，实际 ZIP 解压后启动两次、每次 21 项窗口检查通过；签名、架构、存档复开及本地下载哈希/CRC 检查通过。详细证据为 `outputs/XiaohanDesktop/verification-macos.json`，真实输入和人工外观验收仍未完成。

仓库使用 `source.zip` 初始源码快照加 `mac-fixes.patch` 组装已验证源码。初始快照对应本地 `outputs/小汉-Mac构建源码.zip`，SHA256 为 `e136675f469f25f1ad56236cb5654a98ea8d761dd6a74c78fa4b08bce292efe0`；快照内的“尚未构建”说明是上传前历史状态。当前本地工程已包含测试修正。首轮失败来自测试未解析 macOS 临时路径符号链接，修正预期路径后完整重跑通过，没有绕过失败检查。

## 准备上传的范围

仅包含 `app` 下的运行源码、测试、运行必需 PNG 与捡球定位 JSON，以及构建脚本、使用说明和工作流。不包含原始照片、用户存档、生成提示词、本机快捷方式、Windows 安装包或任何凭据。上传应使用用户确认的私有仓库。

工作流仅通过 `workflow_dispatch` 手动运行，分别使用 GitHub 的 `macos-15`（M 系列）和 `macos-15-intel`（Intel）标准 runner，单任务最多 20 分钟。仓库权限为只读，不发布公开 Release，构建产物保留 7 天。运行会使用账户 GitHub Actions 额度，计费与可用额度须在启动前核对。

## 构建与验收

在 macOS 15 或以上、Python 3.11 的环境中：

```sh
python -m pip install -r requirements.txt
(cd app && python -m unittest discover -s tests -v)
python build_mac.py
python check_mac.py
```

GitHub 中在 Actions 选择 Build Xiaohan for Mac，再执行 Run workflow。两种架构独立构建，单元测试、应用打包、解压后的真实窗口检查任一步失败，该架构不会上传为已验证产物。成功后下载对应 artifact，里面的 `小汉-macOS-arm64.zip` 或 `小汉-macOS-x86_64.zip` 才是朋友使用的包。

检查使用隔离 HOME，验证初次启动、保存重开、透明属性、窗口与照顾入口、出游及捡球渲染。自动化不读取或绕过 macOS 权限设置，也不伪造真实键盘输入验收。真实打字联动、透明边缘观感、鼠标穿透行为、不同屏幕缩放及首次下载后的 Gatekeeper 流程仍需 Mac 用户确认。最终版本需反馈这些未验证项。

应用采用 ad-hoc 签名保证包结构完整，未做 Apple Developer ID 签名或公证。打包脚本通过 `ditto` 保留 .app 中的符号链接和执行权限；解压检查重新校验签名。存档保存在应用外的 `~/Library/Application Support/XiaohanDesktop/pet.json`，避免改写已签名应用。

## Mac 适配

桌面使用 Tk 的 `-transparent` 和 `systemTransparent`，保留图片 alpha；中文字体使用 PingFang SC。支持右键、Control+点击和 Command+Q。使用文件锁限制同一存档的多个实例。

打字联动使用 Quartz 的按键次数统计，每 25ms 读取差值，不获取按键内容；休息与成长使用系统空闲时长。Mac 统计不包含长按自动重复，修饰键也不作为普通打字。首次读取只建立基线，不将历史按键误认为刚输入。Quartz 接口可调用和监听线程启动已经云端验证，真实打字联动仍待接收者试用。

依据：[PyInstaller 平台构建要求](https://pyinstaller.org/en/stable/operating-mode.html)、[Tk 透明窗口](https://www.tcl-lang.org/man/tcl8.6/TkCmd/wm.htm)、[Apple 按键计数接口](https://developer.apple.com/documentation/coregraphics/cgeventsource/counterforeventtype(_:eventtype:))、[GitHub runner 平台](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-actions-run/choosing-github-hosted-runners)、[Apple 首次打开应用](https://support.apple.com/en-us/102445)。
