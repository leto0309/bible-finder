# 经文来源

离线数据于 2026-10-21 从 GetBible v2 获取。上游目录明确将下列三个译本标为 **Public Domain**。应用不访问参考网站的接口或抓取其经文。

| 数据标识 | 译本 | 上游版本 | 经节数 | 直接数据 |
| --- | --- | --- | --- | --- |
| cus | 和合本简体 | 3.1 / 2023-10-28 | 31,103 | https://api.getbible.net/v2/cus.json |
| cut | 和合本繁体 | 3.1 / 2023-10-28 | 31,103 | https://api.getbible.net/v2/cut.json |
| web | World English Bible | 3.1 / 2012-01-25 | 31,095 | https://api.getbible.net/v2/web.json |

许可与版本目录：https://api.getbible.net/v2/translations.json 。中文数据源标注 bible.fhl.net；WEB 标注 ebible.org/web/。完整原始元数据保存在 `src/appcore/data/sources.json`，包括上游版本历史、上游 SHA、下载内容 SHA256、各书章节数和最终 DB SHA256。

三个译本均有 66 卷、1,189 章；31,095 与 31,103 的节数差异保留上游编节。没有以另一译本填充或生成缺失经节。软件不宣称文本零错或与参考网站结果数量完全一致。

导入处理仅剥离开头 BOM、去除中文排版空白（包括 SWORD 繁体文本的词间空格），英文连续空白合并为单个空格；没有翻译、改写、生成经文。搜索索引额外做 Unicode NFKC 规范化。

如需重建，下载上述三个 JSON 和目录到 `work/sources/`，先核对现有 sources.json 中的 SHA256，再运行：

```powershell
python scripts/import_bibles.py --source work/sources --output work/rebuilt/bible.sqlite3
```

导入器拒绝覆盖已存在的目标文件；更换数据版本前检查许可、章节与测试结果。现有发布包在构建及运行时均不下载数据。

感谢 GetBible、CrossWire、信望爱与 World English Bible 的公共经文资源。本软件与这些组织及耶大雅网站无隶属关系。
