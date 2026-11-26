# 小汉桌面宠物 · Mac 分享版

2026-11-16 扔球更新调整了追球步频、弧线转身与叼球跑姿的衔接。M 系列及 Intel 版本已构建，适用 macOS 15 或更新系统。下载对应 [Actions 构建产物](https://github.com/xingtianxiang/xiaohan-desktop/actions/runs/43794365570)，其中内层 `小汉-macOS-arm64.zip` 或 `小汉-macOS-x86_64.zip` 为分享包。完整解压，将小汉.app 拖入应用程序，无需安装 Python。

构建提交：`4ec25cf93279d4ab727cf12d7dad3ad21a3ba9cc`。每种架构 53 项单元测试通过；最终 ZIP 解压后启动两次，每次 21 项窗口检查通过。签名完整性、CPU 架构、初始存档和保存复开均已验证。真实键盘联动、不同显示缩放及人工外观验收仍需接收者确认。

仓库通过 `source.zip` + `mac-fixes.patch` 组装源码，`.github/workflows/macos.yml` 为有效云端入口。首轮测试因 macOS 临时目录符号链接导致预期路径不同，已修正测试为解析后的路径并完整重跑。源码快照内部的状态说明保留上传前历史，当前结果以本文件和运行记录为准。

工作流仅手动触发，M 系列和 Intel 分开运行，单任务最多 20 分钟；测试、打包或解压启动失败均阻止交付。Mac 构建产物保留 7 天，不发布到 Release。源码仅含运行代码、必要图片与测试，不包含个人存档或原始照片。

应用使用 ad-hoc 签名，未做 Apple Developer ID 签名或公证。首次打开可能被系统拦截；确认来源后在系统设置 → 隐私与安全性中按提示允许。存档位于 `~/Library/Application Support/XiaohanDesktop/pet.json`。

校验值（SHA256）：

- arm64：`24d6d15d924eb2691942531bf95a5040138e6b3dd18c10d28be9af12812bbf64`
- x86_64：`908dd9bee2b9483a84c9a59b5b349429a841ae00e8958aadf2fbff2222820b1e`

## 仓库结构

- `outputs/XiaohanDesktop`：Windows 和 Mac 共用的源码、运行素材与测试，玩法和验证说明见该目录的 README。
- `work/`：素材导出、便携打包、Mac 源码导出和窗口检查脚本。
- `source.zip` 与 `mac-fixes.patch`：2026-11-16 Mac 构建所用的源码快照。`.github/workflows/macos.yml` 仍从它构建，尚不包含之后加入的拔河连击、跳舞、退出告别和存档修复。
- Windows 便携版从 1.1.0 起通过本仓库的 Releases 发布。已安装的 1.1.0 及以后版本会读取最新 Release 里的 `latest.json`，在“更多”里提示更新；发布步骤见 `outputs/XiaohanDesktop/README.md` 的“版本与远程更新”。
- 个人存档、原始照片、预览视频、分享包和验证截图只保留在本地，规则见 `.gitignore`。
