# 开源参考与借鉴

## 1. imagededup (idealo)

- **仓库**: https://github.com/idealo/imagededup
- **许可证**: Apache 2.0
- **参考版本**: master 分支，约 360 commits
- **借鉴设计**:
  - 多种哈希算法（PHash, DHash, WHash, AHash）的统一 API 封装思路
  - `find_duplicates(encoding_map)` 的接口风格
  - 评估框架概念（提供 ground truth 对比）
- **本项目自行实现**:
  - 不依赖 TensorFlow/CNN，仅使用感知哈希
  - 完全不同的保留策略系统（像素面积优先 + 自定义规则链）
  - CLI + Web 界面而非纯 Python API
  - 文件操作安全保护（默认只读、同名保护、操作计划预览）
  - GitHub API 集成报告

## 2. Duplicate-Imager (Mystic-del12)

- **仓库**: https://github.com/Mystic-del12/Duplicate-Imager
- **许可证**: MIT
- **参考版本**: 2026年2月版
- **借鉴设计**:
  - 多线程处理 + tqdm 进度条的 CLI 体验
  - Dry-run 模式先预览再执行的安全理念
  - 按分辨率/文件大小等多维度自动选择保留文件的思路
- **本项目自行实现**:
  - 不同的保留策略链机制（可组合、可测试的独立策略）
  - 完整的不覆盖同名保护
  - 操作计划（Operation Plan）概念：先计算完整计划，用户确认后再执行
  - 结构化 JSON/HTML 报告替代 CSV

## 3. IMG Dupe Killer (Araden14)

- **仓库**: https://github.com/Araden14/imgdupekiller
- **许可证**: MIT
- **参考版本**: 主分支
- **借鉴设计**:
  - 默认 dry-run 的安全设计哲学
  - 智能保留逻辑：优先保留无尺寸后缀的原图
- **本项目自行实现**:
  - 保留策略从"文件名规则"提升为"像素面积 + 确定性回退"
  - 明确区分"完全重复"和"相似候选"两种场景的不同处理
  - 不执行任何删除操作（仅移动/复制/链接）

## 关于本项目与既有私有项目的关系

本仓库是基于作者私有项目 `SuQingLan/image-similarity-dedup`（Python 3.14 维护版）
的算法基础，重新设计架构开发的独立公开版本。两者关系：

- 相同的核心算法思路：MD5 + pHash 两阶段检测
- 私有项目为 PySide6 桌面 GUI 应用；本项目为 CLI + Web 界面的模块化工具
- 本项目新增：像素面积保留规则、操作计划预览、HTML/JSON 报告、GitHub API 集成
- 本项目移除：Qt GUI、Windows 特有依赖（pywin32、COM 快捷方式）
- 私有仓库保持可见性不变，本项目 README 中说明演进关系