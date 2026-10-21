"""Explicit aliases avoid confusing John with 1/2/3 John."""

_BOOKS = """
创世记|創世記|创 創|Genesis Gen Ge Gn
出埃及记|出埃及記|出|Exodus Exod Exo Ex
利未记|利未記|利|Leviticus Lev Le Lv
民数记|民數記|民|Numbers Num Nu Nm
申命记|申命記|申|Deuteronomy Deut Dt
约书亚记|約書亞記|书 書|Joshua Josh Jos
士师记|士師記|士|Judges Judg Jdg
路得记|路得記|得|Ruth Ru
撒母耳记上|撒母耳記上|撒上|1Samuel 1Sam 1Sa
撒母耳记下|撒母耳記下|撒下|2Samuel 2Sam 2Sa
列王纪上|列王紀上|王上|1Kings 1Kgs 1Ki
列王纪下|列王紀下|王下|2Kings 2Kgs 2Ki
历代志上|歷代志上|代上|1Chronicles 1Chron 1Chr 1Ch
历代志下|歷代志下|代下|2Chronicles 2Chron 2Chr 2Ch
以斯拉记|以斯拉記|拉|Ezra Ezr
尼希米记|尼希米記|尼|Nehemiah Neh Ne
以斯帖记|以斯帖記|斯|Esther Esth Est
约伯记|約伯記|伯|Job Jb
诗篇|詩篇|诗 詩|Psalms Psalm Psa Ps
箴言|箴言|箴|Proverbs Prov Pro Pr
传道书|傳道書|传 傳|Ecclesiastes Eccl Ecc Ec
雅歌|雅歌|歌|SongofSolomon SongofSongs Song SOS
以赛亚书|以賽亞書|赛 賽|Isaiah Isa Is
耶利米书|耶利米書|耶|Jeremiah Jer Je
耶利米哀歌|耶利米哀歌|哀|Lamentations Lam La
以西结书|以西結書|结 結|Ezekiel Ezek Eze Ezk
但以理书|但以理書|但|Daniel Dan Da Dn
何西阿书|何西阿書|何|Hosea Hos Ho
约珥书|約珥書|珥|Joel Joe Jl
阿摩司书|阿摩司書|摩|Amos Am
俄巴底亚书|俄巴底亞書|俄|Obadiah Obad Ob
约拿书|約拿書|拿|Jonah Jon Jnh
弥迦书|彌迦書|弥 彌|Micah Mic Mi
那鸿书|那鴻書|鸿 鴻|Nahum Nah Na
哈巴谷书|哈巴谷書|哈|Habakkuk Hab Hb
西番雅书|西番雅書|番|Zephaniah Zeph Zep Zp
哈该书|哈該書|该 該|Haggai Hag Hg
撒迦利亚书|撒迦利亞書|亚 亞|Zechariah Zech Zec Zc
玛拉基书|瑪拉基書|玛 瑪|Malachi Mal Ml
马太福音|馬太福音|太|Matthew Matt Mat Mt
马可福音|馬可福音|可|Mark Mar Mk Mr
路加福音|路加福音|路|Luke Luk Lk
约翰福音|約翰福音|约 約|John Joh Jn
使徒行传|使徒行傳|徒|Acts Act Ac
罗马书|羅馬書|罗 羅 罗马人书 羅馬人書|Romans Rom Ro Rm
哥林多前书|哥林多前書|林前|1Corinthians 1Cor 1Co
哥林多后书|哥林多後書|林后 林後|2Corinthians 2Cor 2Co
加拉太书|加拉太書|加|Galatians Gal Ga
以弗所书|以弗所書|弗|Ephesians Eph Ep
腓立比书|腓立比書|腓|Philippians Phil Php
歌罗西书|歌羅西書|西|Colossians Col Co
帖撒罗尼迦前书|帖撒羅尼迦前書|帖前|1Thessalonians 1Thess 1Th
帖撒罗尼迦后书|帖撒羅尼迦後書|帖后 帖後|2Thessalonians 2Thess 2Th
提摩太前书|提摩太前書|提前|1Timothy 1Tim 1Ti
提摩太后书|提摩太後書|提后 提後|2Timothy 2Tim 2Ti
提多书|提多書|多|Titus Tit Ti
腓利门书|腓利門書|门 門|Philemon Philem Phlm Phm
希伯来书|希伯來書|来 來|Hebrews Heb He
雅各书|雅各書|雅|James Jas Jam Jm
彼得前书|彼得前書|彼前|1Peter 1Pet 1Pe 1Pt
彼得后书|彼得後書|彼后 彼後|2Peter 2Pet 2Pe 2Pt
约翰一书|約翰一書|约一 約一|1John 1Jn 1Jo
约翰二书|約翰二書|约二 約二|2John 2Jn 2Jo
约翰三书|約翰三書|约三 約三|3John 3Jn 3Jo
犹大书|猶大書|犹 猶|Jude Jud
启示录|啟示錄|启 啟|Revelation Rev Re
""".strip().splitlines()

BOOKS = []
ALIASES = {}
for number, line in enumerate(_BOOKS, 1):
    simplified, traditional, short, english = line.split("|")
    BOOKS.append((number, simplified, traditional))
    for alias in [simplified, traditional, *short.split(), *english.split()]:
        ALIASES[alias.casefold()] = number


def book_name(book: int, version: str = "cus") -> str:
    return BOOKS[book - 1][2 if version == "cut" else 1]
