# 架构

- `app.py` / `appcore.main`：启动、便携数据目录、自检与 GUI 冒烟测试。
- `books.py`：66 卷中英名称和显式别名；不靠模糊匹配猜书名。
- `engine.py`：经文引用解析、范围验证、参数化 SQLite 查询、20 节分页、章节导航。每次操作独立只读连接。
- `ui.py`：原生 Tk 桌面窗口。单工作线程执行搜索，队列回传结果，递增请求编号丢弃过期结果。Tk 操作只在主线程。
- `preferences.py`：原子写入收藏与偏好，失败时回滚内存收藏，保留不可读文件。
- `profile_lock.py`：每个数据目录持有 OS 级独占锁，直到窗口退出，避免多窗口静默覆盖收藏。
- `data/bible.sqlite3`：三译本离线数据库；`sources.json` 保存来源、版本、上游 SHA、下载文件 SHA256 和 DB SHA256。
- `scripts/import_bibles.py`：维护者显式运行的数据导入器，验证完整书卷、章节、唯一键与许可；应用启动不下载数据。

保留上游逐节编号与字词，只去除中文排版空白、合并英文重复空白。`search_text` 额外做 NFKC 归一化；显示文本不做词义或译文修改。WEB 的节数差异来自上游编节。

基于工厂 Python 模板，项目独立存放，功能开发在 Git Worktree；verify、build、package 使用项目保存的工厂脚本。PyInstaller 打包为一个 Windows GUI EXE，数据资源以 appcore 相对路径定位。打包的 Python/Tcl/Tk 许可随 Release 提供。运行期仅标准库。
