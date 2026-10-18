# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

## [0.2.0] - 2026-10-18

### Added

- **GitHub API 集成**（`github_integration.py`）：扫描完成后可向指定仓库自动创建 Issue（查重摘要）。
  - `--gh-repo owner/repo` + `GITHUB_TOKEN`（或 `--gh-token`）触发；
  - 纯标准库实现（urllib），零新增依赖；
  - token 从环境变量读取，绝不写入报告；无 token 时优雅跳过（返回码 2）；
  - 认证失败/余额不足不自动重试。
- 6 项 GitHub 集成单元测试（mock 网络调用：token 读取、Issue body 生成、POST 请求、HTTP 错误处理）。

## [0.1.0] - 2026-10-18

### Added

- 项目初始公开版本，从私有项目 `image-similarity-dedup` 的算法基础独立设计。
- MD5 完全重复检测 + pHash 感知哈希相似检索两阶段流水线。
- 可组合保留策略链：像素面积 → 文件字节大小 → 字典序（`selector.py`）。
  - **与私有版本的关键差异**：私有版本按文件字节大小保留；公开版本默认按像素面积保留，同面积回退字节大小。
  - 像素面积不等于画质评分，已在 README 明确说明。
- 分组规则：完全重复按 MD5 分组；相似按两两相似度严格大于阈值分组。
- 安全文件操作：默认只读；复制/移动永不覆盖（自动编号）；移动失败保留源文件；操作计划预览。
- JSON + HTML 双格式报告。
- CLI：`visual-dedup`，支持阈值、哈希参数、线程数、扩展名、dry-run/execute。
- 19 项自动化测试（含"小图字节更大"回归样例）。
- 示例图片生成脚本 `examples/generate_samples.py`。
- GitHub Actions CI（Python 3.10/3.12/3.14，单测 + CLI 端到端）。
- MIT 许可证与第三方依赖声明。

### Known Differences from Private Project

| 维度 | 私有项目 image-similarity-dedup | 本公开项目 |
|------|-------------------------------|-----------|
| 界面 | PySide6 桌面 GUI | CLI + HTML/JSON 报告 |
| 保留规则 | 文件字节大小 | 像素面积 → 字节大小 → 字典序 |
| 平台 | Windows（pywin32、COM 快捷方式） | 跨平台 |
| 文件操作 | 复制/剪切/快捷方式 | 复制/移动 + 操作计划 |
| 删除 | 未启用 | 不支持（无删除操作） |