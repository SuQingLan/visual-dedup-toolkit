# 项目讲解稿：visual-dedup-toolkit

## 1. 解决什么问题

本地图片库和数据集常混有大量重复与相似图片：手机相册的连拍、从网络保存的同图不同尺寸、压缩前后版本、跨目录拷贝的副本。手动清理几乎不可能，而"看到重复就删"的工具又太危险——一旦误删唯一原图就不可逆。

本工具提供**两阶段检测 + 安全整理**：
1. MD5 精确识别字节完全相同的文件（100% 准确、无歧义）。
2. 感知哈希（pHash）检索视觉相似图片（容忍缩放、压缩、轻微编辑）。

然后把"保留哪张、移动哪些"交给可配置的**保留策略链**，并以**操作计划**形式先预览、后执行，默认完全只读。

## 2. 关键设计

### 两阶段哈希为什么快
- MD5 是 O(n) 流式计算，先剔除完全重复。
- 每个 MD5 组只取一个代表文件算 pHash（m ≪ n 个代表），再两两比较。
- 相似比较只在代表之间做，避免同内容反复哈希。

### 保留策略是"函数链"而非硬编码规则
每个策略是 `List[Path] -> Optional[Path]`：决定不了就返回 None 交给下一个。
默认链：**像素面积（宽×高）→ 文件字节大小 → 字典序**。

> ⚠️ 像素面积 ≠ 画质评分。大而模糊的图可能比小而清晰的图像素更多。它是"更大通常更清晰"的启发式，文档与 README 均明确声明。

### 安全的默认行为
- 默认只读：只生成报告，绝不触碰文件。
- 整理必须显式传参 + `--execute`。
- 复制/移动**永不覆盖**已有文件（自动加 `(1)` 编号）。
- 移动失败时源文件保留（跨盘先复制、成功后删源）。
- 操作计划（Operation Plan）先 dry-run 预览、再 execute。

### 分组语义
沿用私有项目的"每图至多一个相似组"策略，避免传递闭包把互不相似的端点硬并进一组（A≈B、B≈C、A≉C 时 A、C 不强行同组）。

## 3. 实际贡献（区别于既有资产）

| 内容 | 说明 |
|------|------|
| 像素面积保留规则 | 私有项目按文件字节大小保留；本项目实现像素面积优先 + 回归测试（"小图字节更大"样例） |
| 模块化架构 | scanner/hashing/grouper/selector/organizer/reporter/webui 七模块，单向依赖 |
| 操作计划机制 | 独立于 GUI 的安全整理流程 |
| 双格式报告 | JSON + HTML + 浏览器预览 UI |
| 测试 | 26 项，含报告键结构回归、URL 编码缩略图回归 |

## 4. 踩过的坑（真实记录）

1. **MD5 代表文件选择不确定**：最初取 `paths[0]`，依赖线程完成顺序，同组代表可能漂移。改为 `sorted(paths)[0]`，确定性输入 → 确定性输出。
2. **JSON 报告键冲突**：`similar_groups` 同时当计数和数组用，计数被静默覆盖。改名 `similar_group_count` 并加回归测试。
3. **webui 缩略图 404**：Windows/CJK/空格路径在 URL 中被编码，未 `unquote` 直接拼文件路径导致 404。
4. **沙箱限制**：Windows 沙箱禁止绑定套接字（WinError 10013），webui 改用直接调用 handler 验证。
5. **pHash 纯色图边界**：hash_size=8 时纯红与纯蓝可哈希相同；测试改用结构化图案。

## 5. 如何演示

```bash
# 1) 生成示例（7 文件：原图/字节副本/缩略/放大/异图/损坏/非图片）
python examples/generate_samples.py test_images

# 2) 只读扫描（10 秒内出报告）
visual-dedup test_images -o dedup-report

# 3) 打开报告
open dedup-report/report.html          # 或启动预览 UI
python -m visual_dedup.webui dedup-report/report.json --root test_images

# 4) 演示安全整理（先预览）
visual-dedup test_images --move-duplicates out/dup --move-similar out/sim   # dry-run
visual-dedup test_images --move-duplicates out/dup --move-similar out/sim --execute
```

演示要点：相似组保留 `resized_128.png`（像素面积最大）而非字节更大者；损坏图被跳过并记录；dry-run 不产生任何副作用。
