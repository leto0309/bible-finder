# 寻经 Bible Finder

Windows 免安装、完全离线的圣经经文查询工具。支持经文出处、关键词、整章阅读和本机收藏。无需账号、Python、网络连接或付费 API。

![寻经桌面界面](docs/images/app.png)

## 下载与使用

在本仓库 **Releases** 下载 `BibleFinder-1.0.0-windows-x64.zip`，解压到一个可写入的文件夹，双击 `bible-finder.exe`。

- 支持 Windows 10 / 11，x64；不需要管理员权限。
- 三个完整译本：和合本简体、和合本繁体、World English Bible（WEB）。每个译本均有 66 卷、1,189 章。
- 收藏与偏好保存到程序旁的 `BibleFinder-data/settings.json`，迁移软件时一并复制该文件夹。
- 退出后删除程序目录即可移除软件；保留 `BibleFinder-data` 可保留收藏。
- 当前版本未做代码签名；请通过本仓库 Release 和 SHA256 校验下载来源。

## 查询示例

| 输入 | 功能 |
| --- | --- |
| `约 3:16` / `約3:16` / `John 3:16` | 查询单节 |
| `约翰福音3章16节` | 中文章、节格式，使用阿拉伯数字 |
| `John 3:16-18` | 连续经节 |
| `约3:36-4:2` | 同一书卷内跨章范围 |
| `诗篇23` | 查询整章 |
| `先知` / `God so loved` | 关键词或连续短语 |

关键词可限定整本、旧约、新约或指定书卷，结果每页 20 节，显示总数和耗时。英文搜索忽略大小写，中文搜索忽略排版空白；**简体与繁体关键词须与所选译本一致**。`%`、`_` 等字符按字面匹配，不是通配符。不支持语义搜索、多段经文合并或中文数字章号。

经文出处优先于关键词范围。点击结果可复制带出处和译本的经文、收藏；双击结果或点击「阅读整章」查看上下文。阅读模式可按书卷、章节导航，并跨书卷翻章。收藏页显示所有译本的收藏。

快捷键：`Ctrl+F` 聚焦查询，`Enter` 查找，`Ctrl+D` 收藏/取消收藏当前经文。`A−` / `A+` 调整阅读字号。

## 数据与许可

程序源码采用 [MIT](LICENSE)。经文数据独立许可为 Public Domain，来自 [GetBible v2](https://getbible.net/api/bible/v2/) / CrossWire SWORD，并保留上游元数据、版本及 SHA256。详见 [数据来源](docs/data-sources.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。

本软件独立实现核心查询功能，功能参考 [耶大雅圣经工具](https://bibletool.konline.org/query)，不使用其接口、代码、品牌或网站经文库，与其无隶属关系。不包含未获再分发授权的现代译本。

## 从源码运行

Python 3.11+，标准库包含 Tk（Windows 官方 Python 安装器自带）。

```powershell
python app.py
python app.py --self-test
```

开发与构建（PowerShell 7.2+）：

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements-dev.txt
./scripts/verify.ps1
./scripts/build.ps1
./scripts/package.ps1
```

构建 wheel / sdist 到 `build/`，打包 Windows 单文件程序到 `dist/bible-finder.exe`。`scripts/package.ps1` 先执行验证和构建；发布 ZIP 使用 `python scripts/make_release.py`。项目沿用 AI Dev Factory 脚本，已为本软件加入数据库打包参数。

GUI 冒烟检查（使用独立的测试收藏目录）：

```powershell
python app.py --smoke-test --profile-dir work/smoke-profile --report work/gui-test.json
```

`--self-test` 和 `--smoke-test` 也可直接传给 EXE；加 `--report` 可输出 JSON 结果。Linux CI 只检查查询核心与构建，Windows CI 还运行 GUI 冒烟测试。

## 隐私

程序运行时不请求网络、不上传查询或收藏、不含遥测。离线数据库只读，收藏原子写入；损坏的收藏文件会保留并显示错误，不会静默覆盖。可通过 `--profile-dir` 指定另一个本机数据目录。
