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

来源、固定提交、缺失字段和使用边界见[精简库说明](精简词库/README.md#数据来源与使用边界)。各来源保留自己的权利说明；本仓库没有用一个统一许可证覆盖第三方词典或教材内容。
