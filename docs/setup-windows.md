# Windows 环境

终端用户仅需 Windows 10/11 x64，解压运行，不需安装运行时或管理员权限。

开发需 Python 3.11+（含 Tcl/Tk）、PowerShell 7.2+、Git。安装 requirements-dev.txt 后使用 scripts/verify.ps1、build.ps1、package.ps1。无需 Node/.NET。

本机部署使用已安装的 AI Dev Factory 环境，先加载工厂 Enter-Factory.ps1 -NoLocation，复用其 Python venv。工厂脚本重定向测试 TEMP 到受允许的工作目录；沙箱内手动运行 pytest 时，可用 `--basetemp work/test-temp` 避免系统临时目录重命名限制。
