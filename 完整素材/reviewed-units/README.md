# 外研教材按单元词表

本目录保存与指定教材 PDF 对照的词条、单元、页码和版次。`catalog.json` 是合并目录；每册 `books/*.json` 含完整的本册主词表，按 `unit` 筛选即可学习对应单元。不能将陈琳版与孙有中版互相替代。

## 单元与收录范围

- 陈琳 2011 课标：小学三至六年级上下册，初中七至九年级上下册。小学原书按 Module 列词，没有猜分成课内 Unit 1/2；初中按原书词条页码及课时起始页定位 Module / Unit。
- 孙有中 2022 课标：以已核验的官方 PDF 为准，优先三年级和七年级。Welcome、Starter、Unit 保持原表分组。`sources/fltrp-sun-manifest.json` 列明本批已收录册次、每组条数及 PDF 哈希。
- 本批官方目录提供小学三、四、五年级上下册及六上，初中七、八年级上下册及九上；没有六下和九下资源。未收录册不能用旧版冒充。目录年度不是出版年份，版权页空白的印次明确留为未知。
- 每册核验说明列明专名、歌曲、戏剧、分级阅读和字母序重复表的处理。单元主词表包含原表非加粗词与词组，不只抽取加粗词。
- 单词保留大小写、短语及符号。原表括号中的变体按各册说明放入释义。小学原表没有音标，仅按精确词形从现有词典补充并注明来源；新版初中尚未逐条核验扫描音标，留空，避免将 OCR 字符误标为教材音标。

## 可追溯的数据

`ordinal` 是本词表次序，`pdfPage` 是 PDF 的 1 起始页码（可能不同于书内页码），`unit` 是可筛选单元。每册目录保留来源链接、PDF SHA-256、核验页范围和版次；原始逐页转录保存在 `sources/*.tsv`。旧版初中的生成依据另见 `fltrp-middle-sources.json`。

教材 PDF 保存在本机临时核验目录，不嵌入游戏。登录信息只由本机已有解析器管理，不进入源数据或导出结果。

## 重建与核对

从 small-games 根目录运行：

```powershell
python assets/english-dict/完整素材/reviewed-units/build_primary.py
python assets/english-dict/完整素材/scripts/review_fltrp_middle.py --check
python assets/english-dict/完整素材/scripts/review_fltrp_sun.py --check --pdf-dir .scratch/release-textbooks
python assets/english-dict/完整素材/reviewed-units/merge_catalog.py
pnpm --filter ciyu-word-tiles vocabulary:sync
pnpm --filter ciyu-word-tiles test
```

孙有中转录变更后去掉 `--check` 重建，再执行核对。旧版初中需重建时传 `--pdf-dir .scratch/release-textbooks`，要求原 PDF 哈希一致；已有数据的静态检查无需联网。

词屿按册下载核验哈希；每单元分成最多 6 词、80 牌的连续批次，最后一批可以只有 1 词。游戏词库与本目录 JSON 逐字节一致，历史 SQLite 的 22 份旧词表另列为仅整册资源。运行 `pnpm --filter ciyu-word-tiles test:library:browser` 可用真实触控验证新版三上 Welcome 全部 31 词、尾批、刷新、提示词复习和已缓存书的断网练习。
