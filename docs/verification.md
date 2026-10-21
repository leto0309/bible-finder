# 1.0.0 验证记录

本地验证日期：2026-10-21。环境：Windows x64、Python 3.11.4、PyInstaller 6.22.3，使用已部署 AI Dev Factory。

## 已执行

- Factory verify：39 项 pytest 测试通过，compileall、ruff、自检通过。
- Factory build：sdist 和 wheel 构建成功，包含完整离线数据库。
- Factory package：Windows 单文件 GUI EXE 构建成功。
- 打包后的 EXE `--self-test`：三个译本、经文范围、完整性、关键词检索通过。
- 打包后的 EXE `--smoke-test`：异步查询、分页、整章上下文、剪贴板、收藏、章节边界和译本切换通过。
- 独立只读审查：发现同目录多实例可能覆盖收藏，已加 OS 文件锁；复核与新增锁测试通过。额外验证旧搜索不能覆盖新阅读状态、译本切换保持章节、收藏保持原译本。
- 实际桌面窗口检查：发现高 DPI 下底部操作被裁切，已调整空间分配，重新打包及 GUI 冒烟检查通过；实际确认上下文与字号按钮可见。
- actionlint：CI / Release / PR 工作流语法检查通过。
- 基础机密扫描及 gitleaks 历史扫描通过；发布前再次扫描最终提交。

所有 93,301 节数据来自列明的公共领域来源，没有生成或补写经文。源数据校验值、数据库校验值在 sources.json；EXE 与发布 ZIP 的校验值在 SHA256SUMS.txt。

## 范围

未使用付费 AI API。未在其他 Windows 版本与所有显示比例逐一测试；未代码签名。GitHub 云端 CI 是否完成以仓库 Actions 的实际结果为准，不能由本地通过推定。
