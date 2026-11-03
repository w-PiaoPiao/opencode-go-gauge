# 运行时验证证据索引（release 隐私合规 / 演示模式）

本目录存放「release 构建是否可绕过隐私同意」「演示模式是否可用」的模拟器实测截图，
用于支撑 `docs/runtime-verification.md` §2.4 与发布检查清单。

## A. release 包隐私合规（清理数据后安装 release HAP，DEBUG=false）

| 文件 | 场景 | 结论 |
| --- | --- | --- |
| `smoke-release-A1-first-launch-privacy.jpeg` | 首次启动 | ✅ 弹出隐私政策弹窗（含可点开的《隐私政策》链接） |
| `smoke-release-A2-back-welcome.jpeg` | 关闭弹窗/返回 | ✅ 停留欢迎页，未进入主界面 |
| `smoke-release-A2-privacy-page.jpeg` | 点弹窗内《隐私政策》 | ✅ 进入应用内隐私政策页 |
| `smoke-release-A2-back-dialog.jpeg` | 从隐私页返回 | ✅ 弹窗/同意流程仍在，未被绕过 |
| `smoke-release-A3-declined-welcome.jpeg` | 点「不同意」 | ✅ 停留欢迎页，未联网 |
| `smoke-release-A3-login-reprompt.jpeg` | 拒绝后点「立即登录」 | ✅ 再次弹窗，未同意不得登录 |
| `smoke-release-A4-agreed-welcome.jpeg` | 点「同意并继续」 | ✅ 进入欢迎页（尚未登录），同意态写入本地 |
| `smoke-release-A4-login-webview.jpeg` | 同意后点登录 | ✅ 正常打开 opencode.ai 登录页 |
| `smoke-release-A5-demo-params-privacy.jpeg` / `-demo-params.jpeg` | **强杀后带 `--ps demo 1 ...` 冷启** | ✅ release 仍弹隐私弹窗、无主界面/demo 数据（启动参数被 `BuildProfile.DEBUG` 全部忽略，P0 已修复） |
| `smoke-release-A5-lang-theme-params.jpeg` | 带 `--ps lang en --ps theme dark` 冷启 | ✅ release 忽略语言/主题参数，界面保持默认 |
| `smoke-release-welcome.jpeg` | release 欢迎页（同意后） | ✅ 无演示按钮/调试入口 |

## B. debug 包演示模式（截图/调试用）

| 文件 | 场景 | 结论 |
| --- | --- | --- |
| `smoke-debug-demo-home.jpeg` | debug HAP + `--ps demo 1 ...` | ✅ 正常进入主界面渲染首页，无 crash |

补充：同意后 `privacy_accepted=1` 落盘（`haps/entry/preferences/gogauge`），强杀重启不再弹窗；
release 包内 `BuildProfile.DEBUG=false`，`EntryAbility/Index/AppRoot` 三处均以
`BuildProfile.DEBUG` 守卫启动参数与演示路径。
