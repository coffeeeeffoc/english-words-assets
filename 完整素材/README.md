# 英语词库素材

2026-09-18 抓取了智慧教育平台电子教材目录中的全部小学、初中英语教材元数据（含五四学制）。

- 379 本教材，17,828 个关联音频，共 18,207 个文件，目录标注合计 67.66 GiB。
- `metadata/books.json`：筛选后的教材；`metadata/details/` 与 `metadata/audios/`：官方元数据。
- `metadata/manifest.json`：文件地址、分类、大小、校验值、下载状态。当前均待下载。
- 批量 PDF/音频下载尚未启动；用户说明最终目标为单词、中文释义、音标词库，正在评估直接使用结构化词典。
- 上游解析器：<https://github.com/happycola233/tchMaterial-parser>，固定于 `7d37b0e4de0ccd23cc1e9cd801baecaef43b98f2`。

如果之后仍需下载教材，运行 `.venv/Scripts/python.exe download.py`；重复运行会校验并跳过已完成文件。运行 `download.py --check` 校验落盘文件，`test_download.py` 执行离线自检。当前 F 盘空间不足以存放上述全部 PDF 和音频。

脚本使用解析器本地配置中的登录凭据，凭据未写入本目录。PDF 保留原始字节用于校验。现有清单是本次快照，重新抓取目录需先备份并移开 `metadata/manifest.json` 和详情/音频缓存。
