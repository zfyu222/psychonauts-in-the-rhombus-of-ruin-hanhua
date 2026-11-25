# 脑航员：菱形废墟简体中文汉化工程

- 原名：Psychonauts in the Rhombus of Ruin
- 中文名：脑航员：菱形废墟（暂译）
- 开发商：Double Fine Productions、React Games
- 发行商：Double Fine Productions
- 发行平台：Steam（AppID 788690），Windows VR
- Steam 发售日期：2018-04-19
- 引擎：Unreal Engine 4.12.5（本地 Engine/Build/Build.version）
- 原语言：英语；Steam 标示英文界面、语音及字幕。安装资源另有法语和西班牙语 locres，不据此断言完整支持。
- 资料来源：[Steam 商店](https://store.steampowered.com/app/788690/)

面向汉化维护与二次开发。玩家可在 [GitHub Releases](https://github.com/zfyu222/psychonauts-in-the-rhombus-of-ruin-hanhua/releases/) 获取补丁及安装说明，当前公开版本为 v1.0。

## 修改译文

- [正文译文](psychonauts-in-the-rhombus-of-ruin_text_translated.csv)共 2,694 条，[正文映射](psychonauts-in-the-rhombus-of-ruin_text.mapping.json)记录资源位置和原文 SHA-256。
- [贴图译文](psychonauts-in-the-rhombus-of-ruin_images_text_translated.csv)共 236 条，[贴图映射](psychonauts-in-the-rhombus-of-ruin_images_text.mapping.json)记录对应区域。按现有行序编辑单列 UTF-8 CSV，保留占位符和换行。
- [正文导出校验](TranslateFiles/reports/final_validation.json)记录当前正式译文的哈希。编辑后需重做对应验收，生成与新译文匹配的校验记录。
- [正文术语表](TranslateFiles/glossary/r3/freeze_39f4b12e/built/glossary_reviewed.json)和[贴图术语表](TranslateFiles/image-text/TranslateFiles/glossary/revision_2_501366cd/built/glossary_reviewed.json)供修改时查阅。

## 开发与构建

使用游戏 Steam Build 10833373、Python 3.12、[repak](https://github.com/trumank/repak) 0.2.3 和支持 UE4.12 的 [UAssetAPI](https://github.com/atenfyr/UAssetAPI)。把仓库克隆到 [StaticHanHua](https://github.com/zfyu222/StaticHanHua) 的 `Projects/psychonauts-in-the-rhombus-of-ruin/`，共用解析器位于工作区的 `Tools/localization/`。运行时组包脚本从 `Tools/repak/repak.exe` 调用 repak。

1. 从自己的 Steam 安装提取游戏原始 PAK 中的 `Content/Dialog`、`Content/Localization`、`Config` 和 `Content/BuildMetadata`，保持 PAK 内相对目录结构，放在项目的 `Analysis/extracted/`。[提取报告](Analysis/extraction-report.json)列出了参与正文回填的原件哈希。
2. 在单独工作副本运行[正文提取](Analysis/extract_text.py)。脚本拒绝覆盖现有映射。先在该副本移出已发布的正文映射，完成提取后核对生成映射与已发布版，再把生成的原文 CSV 放回工作工程。
3. 运行 `python Analysis/repack_text.py --verify-source --out Build/source-check` 检查原文往返，再用 `python Analysis/repack_text.py --out Build/text` 生成中文正文与 locres。
4. 菜单通过[界面提取](Analysis/extract_menu_text.py)和[合并脚本](Analysis/merge_menu_locres.py)处理。提取器读取由 UAssetAPI 从 StartScreen 与 PauseRoom 导出的 JSON。[菜单译文](TranslateFiles/ui-text/psychonauts-in-the-rhombus-of-ruin_ui_text_translated.csv)和[键映射](TranslateFiles/ui-text/localization_keys.json)用于修改主菜单与暂停菜单。
5. [运行时组包](Analysis/build_release_runtime.py)需要正文、菜单、头显提示和字体的生成目录，输入和版本哈希写在脚本里。[字体构建](Analysis/build_formal_fonts.py)依赖本地导出的字体资源及工作区资源工具。修订贴图需基于本机游戏资源重做对应成图并按原路径回填。当前公开工程可重做正文回填，完整字体、贴图和发布包还需要这些本地资产及对应构建输入。

公开贴图映射中的证据链接已换成仓库相对路径。发布时的哈希用于追溯原始验收产物。
