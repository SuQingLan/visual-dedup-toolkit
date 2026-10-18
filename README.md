# visual-dedup-toolkit

视觉相似图片检索与安全去重工具。基于 MD5 完全重复检测 + 感知哈希（pHash）相似检索，提供可组合的保留策略、操作计划预览和结构化报告。

> 本仓库是基于作者个人项目 [image-similarity-dedup](https://github.com/SuQingLan/image-similarity-dedup)（私有）的算法基础重新设计的**独立公开版本**。演进关系与差异详见 [docs/references.md](docs/references.md) 与 [CHANGELOG.md](CHANGELOG.md)。

## 特性

- **两阶段检测**：MD5 识别完全重复，pHash 感知哈希检索视觉相似（容忍缩放、轻微压缩）。
- **明确的分组规则**：完全重复按 MD5 分组；相似图片按两两相似度 > 阈值分组（严格大于）。
- **可组合的保留策略**：默认按**像素面积**（宽 × 高）保留最大者；同面积时回退到文件字节大小；再回退到字典序。像素面积不等于画质评分，README 中有明确说明。
- **默认只读**：默认仅扫描并生成报告，不触碰任何文件。
- **操作计划预览**：需要整理时先生成操作计划（Operation Plan），`--dry-run` 预览，`--execute` 才真正执行。
- **文件安全**：复制/移动永不覆盖已有文件（自动加编号），移动失败时保留源文件。
- **结构化报告**：JSON（机器可读）+ HTML（人可读）两种报告。
- **命令行界面**：`visual-dedup` 命令，支持线程数、阈值、哈希参数配置。

## 安装

Python 3.10+，已在 Python 3.14 上验证。

```bash
pip install -e .
```

依赖：Pillow、ImageHash、numpy、scipy、PyWavelets。

## 快速开始

### 1. 生成示例图片

```bash
python examples/generate_samples.py test_images
```

生成 7 个文件：原图、字节完全相同的副本、不同分辨率同内容图片、完全不同图片、损坏图片、非图片文件。

### 2. 运行扫描（只读）

```bash
visual-dedup test_images -o dedup-report
```

输出示例：

```
Scanning: .../test_images
Found 6 images.
Computing MD5 hashes...
Exact duplicate groups: 1
Computing perceptual hashes...
Similar groups: 1
Operation Plan (5 actions):
  [KEEP]  .../original.png
  [KEEP]  .../duplicate.png
  [KEEP]  .../resized_128.png
  [KEEP]  .../resized_64.png
  ...
(Dry run — use --execute to apply operations)
Report saved to: .../dedup-report
Elapsed: 0.99s
```

只读模式下所有文件均为 `[KEEP]`（不触碰任何文件）。相似组中 `resized_128.png`（128×128）按像素面积保留，而不是按文件字节大小。

### 3. 查看报告

```bash
# 打开 HTML 报告
open dedup-report/report.html

# 或读取 JSON
cat dedup-report/report.json

# 或启动浏览器预览（缩略图 + KEEP 标注，需要 --root 指向扫描目录）
python -m visual_dedup.webui dedup-report/report.json --root test_images --port 8765
# 然后浏览器打开 http://127.0.0.1:8765/
```

### 4. 整理文件（先预览再执行）

```bash
# 预览（默认）
visual-dedup test_images -o dedup-report --move-duplicates dedup-report/duplicates

# 真正执行（谨慎）
visual-dedup test_images -o dedup-report --move-duplicates dedup-report/duplicates --execute
```

### 5. GitHub API 集成（提交查重摘要）

扫描完成后可自动向 GitHub 仓库创建 Issue（查重摘要）：

```bash
GITHUB_TOKEN=your_token visual-dedup test_images -o dedup-report \
  --gh-repo owner/repo
```

- token 通过 `GITHUB_TOKEN` 环境变量或 `--gh-token` 提供，**绝不写入任何报告文件**。
- 无 token 时该功能优雅跳过（打印错误、返回码 2），不影响本地扫描结果。
- 使用标准库 `urllib`，零新增依赖；认证失败/余额不足不自动重试。

## 命令行参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `directory` | 扫描目录（必需） | - |
| `-o, --output` | 报告输出目录 | `dedup-report` |
| `--threshold` | 相似度阈值 (0-1) | `0.80` |
| `--hash-size` | pHash 尺寸参数 | `16` |
| `--workers` | 线程数 | `8` |
| `--extensions` | 图片扩展名列表 | jpg jpeg png bmp gif tiff webp |
| `--move-duplicates` | 移动完全重复候选到指定目录 | None |
| `--move-similar` | 移动相似候选到指定目录 | None |
| `--copy-duplicates` | 复制完全重复候选到指定目录 | None |
| `--copy-similar` | 复制相似候选到指定目录 | None |
| `--dry-run` | 预览不执行（默认） | True |
| `--execute` | 实际执行文件操作 | False |

## 测试

```bash
python -m unittest discover -s tests -v
```

当前 19 项测试覆盖：扫描器扩展名/排除目录/递归、MD5 与 pHash 计算、相似度边界、精确重复分组、像素面积保留策略（含"小图字节更大"回归样例）、操作计划预览、复制不覆盖保护、移动失败保留源文件。

## 架构

```
src/visual_dedup/
├── scanner.py    # 图片发现
├── hashing.py    # MD5 / pHash 计算与批量处理
├── grouper.py    # 重复与相似分组
├── selector.py   # 保留策略（像素面积 → 字节大小 → 字典序）
├── organizer.py  # 安全文件操作 + 操作计划
├── reporter.py   # JSON/HTML 报告
└── cli.py        # 命令行入口
```

## 已知限制

- pHash 是启发式哈希，可能误判；相似阈值需根据实际数据调整。
- 相似分组为两两比较（O(n²)），大量图片时耗时增长明显。
- 像素面积不是画质评分；大而模糊的图可能比小而清晰的图像素更多。
- 移动操作改变源文件位置，执行前务必预览操作计划。

## 开源参考

设计参考了 [imagededup](https://github.com/idealo/imagededup)（Apache 2.0）、[Duplicate-Imager](https://github.com/Mystic-del12/Duplicate-Imager)（MIT）、[imgdupekiller](https://github.com/Araden14/imgdupekiller)（MIT）。借鉴细节与自行实现范围见 [docs/references.md](docs/references.md)。第三方库清单见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
