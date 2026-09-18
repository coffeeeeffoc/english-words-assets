# English Words Assets

英语基础词库、教材词表和可复现的原始素材，供 `small-games` 等应用按需使用。

| 目录 | 内容 |
|---|---|
| [精简词库](精简词库/README.md) | `英语词库.sqlite`、使用说明和 ECDICT 许可证；应用从这里读取数据 |
| [完整素材](完整素材/使用说明.md) | 原始 CSV／JSON／ZIP、官方目录、两本 PDF 样本、处理脚本和缺失报告 |

当前包含 770,999 个基础词项、22 份词表、9,974 条词表记录。字段齐全的词表记录为 9,258 条；716 条仍缺音标。379 条官方教材记录中，29 条有旧词表候选、350 条未找到对应词表，尚未核验完整覆盖新版教材。

## 在 small-games 中获取

`assets` 已经是独立素材仓库，词库嵌套在它下面：

```text
small-games/
└── assets/                  # coffeeeeffoc/small-games-assets
    └── english-dict/        # coffeeeeffoc/english-words-assets
        ├── 精简词库/
        └── 完整素材/
```

从 `small-games` 根目录初始化到提交中锁定的版本：

```sh
git submodule update --init --recursive assets
```

应用使用的数据库路径为 `assets/english-dict/精简词库/英语词库.sqlite`。推荐读取 `ready_vocabulary` 视图，它包含词表标识、单词、中文释义、音标和来源；详细字段见[精简库说明](精简词库/README.md)。浏览器和小游戏应用应在构建时导出需要的词表为 JSON，再作为应用资源加载，避免把全部基础词库和中间素材打进应用包。

## 更新引用

先在本仓库提交、推送词库更新；然后依次更新并提交 `small-games-assets` 的 `english-dict` 引用，以及 `small-games` 的 `assets` 引用。普通 `git submodule update` 会恢复锁定版本；只在有意升级词库时拉取新提交。

## 单独克隆与验证

```sh
git clone --recurse-submodules https://github.com/coffeeeeffoc/english-words-assets.git
cd english-words-assets
python 完整素材/scripts/test_build.py
python 完整素材/scripts/verify.py
```

验证仅依赖 Python 标准库。`完整素材/tools/tchMaterial-parser` 以 submodule 固定上游版本；构建精简库不需要启动该 GUI 工具。本机虚拟环境、Python 缓存和未完成下载不提交。

原始资源按原字节保存；两个较大文件（SQLite 和 ECDICT CSV）直接使用普通 Git，无需 Git LFS。

## 数据来源

后续补充或更新素材时，可从以下入口查找。GitHub 仓库主页用于找最新资料，固定提交用于复现本次数据。

| 来源 | 本仓库中的用途 | 本地素材与版本 |
|---|---|---|
| [skywind3000/ECDICT](https://github.com/skywind3000/ECDICT) | 基础英语词条、中文释义和音标；词表缺字段时作为回退来源 | [原始素材](完整素材/sources/ecdict/)，[固定提交 bc015ed](https://github.com/skywind3000/ECDICT/tree/bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b) |
| [kajweb/dict](https://github.com/kajweb/dict) | 已导入的 22 份历史教材及初中／中考词表，保留来源中的释义和英美音标 | [原始 ZIP、解压 JSON 与清单](完整素材/sources/kajweb/)，[固定提交 3992bcb](https://github.com/kajweb/dict/tree/3992bcb94c800a2fd38a9fd6ff95b2353e755363) |
| [国家中小学智慧教育平台·教材](https://basic.smartedu.cn/elecEdu) | 小学、初中英语官方教材目录、下载地址及两本 PDF 样本；用于排查教材覆盖缺口 | [目录元数据](完整素材/metadata/)、[已下载 PDF](完整素材/materials/)、[PDF 提取草稿](完整素材/pdf-extraction/)，本次目录获取日期为 2026-09-18 |
| [happycola233/tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) | 获取上述平台素材的参考工具；不是词典数据来源 | [工具 submodule](完整素材/tools/tchMaterial-parser)，[固定提交 7d37b0e](https://github.com/happycola233/tchMaterial-parser/tree/7d37b0e4de0ccd23cc1e9cd801baecaef43b98f2) |
| [TapXWorld/ChinaTextbook](https://github.com/TapXWorld/ChinaTextbook) | 后续查找历史教材 PDF 的备选入口；本次未从该仓库导入数据 | 未下载，未锁定版本；使用前需核对教材版次 |

重新获取固定版本词典与词表、重建数据库的方法见[完整素材使用说明](完整素材/使用说明.md#本机运行)。需要补教材时，先查看[PDF 后续任务清单](完整素材/reports/pdf-action-plan.csv)，再按需下载和核验；PDF 提取草稿尚未导入正式词表。

来源权利说明、缺失字段和使用边界见[精简库说明](精简词库/README.md#数据来源与使用边界)。各来源保留自己的权利说明；本仓库没有用一个统一许可证覆盖第三方词典或教材内容。
