# 多模态 UGC 最小本地测试系统

本项目使用 Chinese-CLIP ViT-B/16 将中文文本和图片映射到同一语义空间，使用 PaddleOCR 移动模型提取图片文字，并通过 FAISS CPU 完成余弦相似度检索。所有模型、缓存、索引和虚拟环境均保存在当前项目目录，不使用用户目录作为模型缓存。

## 目录结构

```text
intern/
├─ .cache/                # Hugging Face 与 Paddle 缓存
├─ models/                # Chinese-CLIP 本地模型
├─ data/                  # UGC 测试数据
├─ indexes/               # FAISS 索引与元数据
├─ src/                   # 编码、OCR、建库和检索代码
├─ tests/                 # 不依赖模型的快速测试
├─ app.py                 # 命令行入口
└─ requirements.txt
```

## 快速开始

本项目使用 Anaconda 中名为 `ugc-minimal` 的 Python 3.12 独立环境。请先打开 Anaconda PowerShell Prompt，进入项目并激活环境：

```powershell
cd E:\master\intern
conda activate ugc-minimal
python app.py doctor
python app.py download
python app.py demo-data
python app.py build --input data\demo\ugc.jsonl
python app.py search --text "红色圆形" --top-k 3
```

如需把图片中的文字合并到 UGC 文本后再编码：

```powershell
python app.py build --input data\demo\ugc.jsonl --ocr
```

以图片查询：

```powershell
python app.py search --image data\demo\red_circle.png --top-k 3
```

## 数据格式

输入为 UTF-8 JSONL，每行一条 UGC：

```json
{"id":"post-001","text":"公园里的红色圆形装置","image":"red_circle.png"}
```

- `id`：必填且唯一。
- `text`、`image`：至少提供一个。
- 相对图片路径以 JSONL 文件所在目录为基准。
- 同时存在文本和图片时，系统分别编码并对归一化向量取平均，再次归一化。

## 设计说明

- 第一版使用精确内积索引 `IndexFlatIP`；向量均已做 L2 归一化，因此分数等价于余弦相似度。
- OCR 默认关闭，因为图片本身可以直接编码；仅当图片中文字对检索很重要时启用。
- 当前方案适合约 1 万条以内的功能验证。数据规模扩大后，可替换为 FAISS HNSW 或 IVF 索引。

## 小型开源数据集评测

下载并准备 COCO-CN-mini（100组图文对）：

```powershell
python scripts\prepare_eval_datasets.py --dataset coco-cn
```

跨模态检索评测：

```powershell
python app.py evaluate `
  --input data\eval\coco_cn_mini_100\records.jsonl `
  --output reports\coco_cn_mini_100.json --device cpu
```

## 用户画像冷启动模拟

`data\cold_start\users.jsonl` 中包含 6 个模拟初始画像。用户主动选择的兴趣是主要弱先验；
性别、年龄和地区会被保存，但当前不会使用没有行为数据支持的性别/年龄刻板规则。地区只在候选内容
带有 `regions` 字段时参与小幅加权。

使用 COCO-CN Mini 作为候选 UGC，生成每名用户的 Top-5 推荐：

```powershell
python app.py cold-start `
  --users data\cold_start\users.jsonl `
  --candidates data\eval\coco_cn_mini_100\records.jsonl `
  --output reports\cold_start_recommendations.json `
  --top-k 5 --device cpu
```

当前打分由跨模态兴趣语义相似度、可解释兴趣类别匹配、内容热度、内容质量、地域弱先验和少量确定性探索组成。
候选数据未提供热度、质量或地域时分别使用中性默认值，因此本次实验主要验证兴趣画像与 UGC 的
语义匹配。后续接入曝光、点击、停留、点赞、关注和发帖行为后，再逐步由冷启动画像切换到动态画像。

### 生成初始用户标签背包

```powershell
python app.py tag-backpacks `
  --users data\cold_start\users.jsonl `
  --output data\user_profiles\initial_tag_backpacks.jsonl
```

标签背包分别保存消费兴趣、创作兴趣、负向兴趣、证据来源、长期/短期/会话权重和画像阶段。
初始状态只有注册兴趣证据；创作标签和行为权重为空，等待后续发帖与互动事件更新。

### 模拟用户发帖并更新创作标签背包

```powershell
python scripts\simulate_user_posts.py
```

脚本为6个模拟用户各生成2条图文帖子，从帖子文本提取类别标签，并使用发布行为强度、标签置信度、
时间衰减和重复证据衰减更新 `creator_tag_bag`。初始背包保持不变，更新后的背包写入
`data\user_profiles\tag_backpacks_after_posts.jsonl`，明细报告写入
`reports\user_post_simulation.json`。

# 七天热启动行为回放

```powershell
python app.py hot-start-sim `
  --backpacks data\user_profiles\tag_backpacks_after_posts.jsonl `
  --candidates data\eval\coco_cn_mini_100\records.jsonl `
  --final-backpacks data\user_profiles\tag_backpacks_after_7d.jsonl `
  --events data\simulation\hot_start_events_7d.jsonl `
  --output reports\hot_start_7d_simulation.json
```

该命令按时间顺序执行“推荐—反馈—画像更新—重新推荐”，默认模拟6名用户7天、每天10次曝光。

