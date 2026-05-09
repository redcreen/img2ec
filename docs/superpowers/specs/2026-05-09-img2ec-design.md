# img2ec — 国内电商图自动化生成工具

> 设计文档 · 2026-05-09

## 1. 背景与目标

### 1.1 用户场景
小团队/电商运营批量生产电商图，需覆盖**抖店、视频号、淘宝/天猫、小红书** 4 个平台。每个 SKU 需要主图、详情页、视频封面、卖点拼图等多种规格。手工流程：拍图 → PS 套模板 → 改尺寸 → 写文案 → 整理目录，单 SKU 半天起步，30 个 SKU 是周级工作量。

### 1.2 目标
本地 Web 应用，用户上传商品原图，工具自动：
- 智能检测原图类型（白底 vs 拍照），按需去背景
- AI 生成 5 种 aspect ratio 的场景图（master 资产）
- 派生为 4 平台所需的所有尺寸（裁剪/缩放/补白）
- 生成各平台的电商必填字段（标题、副标题、卖点、关键词等）
- 输出按目录组织，可一键 zip 下载
- 浏览器刷新/关闭不影响后台处理

### 1.3 非目标
- 不做 SaaS / 多租户：本地单机或小团队 LAN
- 不做视频本身生成：视频封面只生静态图
- 不做模特换装 / 试衣（V1.1+ 可加）
- 不做商品上架 API 对接（用户自己上架）

## 2. 架构总览

### 2.1 路线（路线 C：解耦推理与编排）
- 业务编排在 FastAPI（mac 本地）
- AI 推理在 ComfyUI（gpu box 远程，Windows）
- LLM 文案在云端 API（GPT-5 / Claude 双路并发）
- 前端 Next.js（mac 本地）

### 2.2 部署拓扑
```
┌──────────────────────────────────┐    ┌────────────────────────┐
│ ① mac 本地（业务/UI 层）         │    │ ② gpu box（远程 Win）  │
│   Next.js 前端 (3000)            │    │   RTX 4080 SUPER 16GB  │
│       ↓ HTTP                     │    │                        │
│   FastAPI (8000)                 │    │   ComfyUI 服务 (8188)  │
│       ↓                          │    │       ↑                │
│   Celery Worker ←→ Redis (6379)  │HTTP│       │ workflow JSON  │
│       ↓                          ├────┤                        │
│   EventBus (内存队列 + webhook)  │    │   模型权重：           │
│   rembg (CPU 抠图)               │    │   Flux dev FP8         │
│   Pillow (派生/叠字)             │    │   SDXL Base 1.0        │
│   SQLite (状态持久化)            │    │   IPAdapter / SAM      │
│   本地文件系统 (artifacts)       │    │                        │
└──────────┬───────────────────────┘    └────────────────────────┘
           │ webhook (事件订阅)
           ↓
┌──────────────────────────────────┐
│ ④ n8n（mac 本地，可选）          │
│   订阅 img2ec 事件做后处理：      │
│   · 上传 OSS / 飞书通知          │
│   · 调 ERP / 上架 API            │
│   也可反向当输入源 → POST /api    │
└──────────────────────────────────┘
                  │
                  ↓ HTTPS（按需）
        ┌─────────────────────────┐
        │ ③ 云端 LLM API          │
        │   OpenAI GPT-5 / Codex  │
        │   Anthropic Claude      │
        │   （VLM 识别 + 文案）   │
        └─────────────────────────┘
```

### 2.3 关键性质
- **后端持久化处理**：浏览器关闭/刷新不影响；状态在 SQLite + Redis
- **Provider 可插拔**：LLM、图像生成、抠图都通过 abstract interface
- **本地优先**：除 LLM API 外都在本地；artifacts 落本地文件系统，可在 Finder 直接访问
- **事件驱动外围**：核心 pipeline 固定（保速度/稳定/可重试），关键节点发 webhook，外部工具（n8n）订阅做自定义后处理 — 灵活性外置而非内嵌

## 3. 输出策略：5 master + N 派生

### 3.1 设计动机
朴素方案：每原图 × 4 平台 × N 尺寸 = 15+ 次 AI 推理。但同 aspect ratio 但不同分辨率的输出，没必要重复生图，缩放裁剪即可。

### 3.2 Master 资产
每张原图固定生成 **5 张 master**（不同 aspect ratio），4 平台共用：

| Master Key | Ratio | 分辨率 | 共用平台 |
|---|---|---|---|
| `1:1` | 1:1 | 1080×1080 | 抖店主图、视频号主图、淘宝主图、小红书 1:1、视频号视频封面 |
| `long` | 750×∞ | 750w 长图 | 4 平台详情页 |
| `3:4` | 3:4 | 900×1200 | 抖店视频封面 3:4、小红书 3:4 |
| `9:16` | 9:16 | 1080×1920 | 抖店视频封面 9:16 |
| `16:9` | 16:9 | 1920×1080 | 淘宝视频封面 16:9 |

### 3.3 平台派生
每平台所需尺寸都从对应 master Pillow 派生（裁剪/缩放/补白），无需 AI：

| 平台 | 输出 | 派生自 |
|---|---|---|
| 抖店 | 主图 1080² + 详情页 750w + 封面 3:4 + 封面 9:16 | 1:1 / long / 3:4 / 9:16 |
| 视频号 | 主图 800² + 详情页 750w + 封面 1:1 + 封面 3:4 | 1:1 / long / 1:1 / 3:4 |
| 淘宝 | 主图 800² + 详情页 750w + 封面 16:9 + 封面 1:1 | 1:1 / long / 16:9 / 1:1 |
| 小红书 | 笔记图 1:1 + 笔记图 3:4 + 长图 750w | 1:1 / 3:4 / long |

总计 **15 个平台输出 / 原图**（每平台 3-4 个）。

### 3.4 收益
- AI 推理：5 次/原图（vs 朴素 15 次）→ **省 67% GPU 时间**
- 调整平台/尺寸：只需改派生表，不重生图

### 3.5 可扩展
将来某品类需要专属尺寸 → 在 `MASTERS` 加新 entry + `DERIVED` 改对应平台映射。

## 4. 场景模板系统

### 4.1 概念
"场景模板"是 AI 生场景图的预设配方：背景描述、光照、风格关键词、可选参考图（IPAdapter）。一个 SKU 选一个场景模板，AI 把商品"放进"这个场景。

### 4.2 SceneTemplate 字段
```python
{
  "id": str,
  "project_id": str,
  "name": str,                   # "大理石台·暖光"
  "category": str,               # "美妆/食品" / "节日·大促" / "3C 数码"
  "desc": str,                   # 用途说明
  "prompt": str,                 # 主 prompt（英文）
  "negative_prompt": str,
  "ref_image_path": str | None,  # IPAdapter 参考图
  "ip_adapter_weight": int,      # 0-100
  "base_model": str,             # "flux-dev-fp8" | "sdxl-base-1.0" | "flux-schnell"
  "created_at": datetime,
  "updated_at": datetime,
}
```

### 4.3 默认场景库（MVP 1 个 + 后续扩充）

**MVP（Phase 1）只内置 1 个**：`大理石台·暖光`
- 类别：美妆/食品（也通用于轻量礼品、小件商品）
- 选这个的理由：①通用度高，跨品类适配；②真正展现 AI 场景生成的价值（不是简单白底替换）；③视觉效果接近真实电商高级感主图
- 用于跑通端到端 pipeline，验证整体流程

**Phase 2 扩充到 16 个**，按品类分组：

| 类别 | 场景 |
|---|---|
| 通用·主图 | 纯白底主图、浅灰渐变背景 |
| 3C 数码 | 极简硬光台面、灰色水泥台·冷光 |
| 美妆/食品 | **大理石台·暖光（MVP 已内置）**、亚麻布料背景 |
| 食品/家居 | 原木桌面·晨光 |
| 户外/运动 | 户外草坪·自然光 |
| 服饰/夏季 | 海边沙滩·黄金时刻 |
| 服饰/书 | 咖啡厅一角 |
| 服饰 | 极简白墙·单衣架、平铺穿搭 |
| 节日·大促 | 双11促销红 |
| 节日·春节 | 春节年货金红 |
| 节日·情人节 | 七夕粉色浪漫 |
| 母婴 | 婴幼柔光场景 |

具体 prompt / negative_prompt 见 `seeds/default_scenes.py`（实现时维护）。

V1.1+ 进一步通过"场景包"机制让用户/社区共享场景库（导入/导出 JSON）。

### 4.4 风格一致性
同一 SKU 下多张原图共用同一场景模板（且共用同一参考图），保证多角度图风格一致。允许用户为单张图覆盖场景（V1.1+ 加）。

## 5. 项目与 SKU 管理

### 5.1 数据模型
```python
Project:
  id, name, desc
  root_path: str          # 本地存储绝对路径
  created_at, updated_at
  # 关联：scenes[], skus[]

SceneTemplate:
  见 §4.2

SKU:
  id, name, project_id
  scene_id                # 整 SKU 共用场景
  status: enum            # draft|ready|running|done|error
  created_at, updated_at
  # 关联：images[]

SourceImage:
  id, sku_id, name, src_path
  status: enum            # pending|cutting|generating|composing|done|failed
  progress: int           # 0-100
  err_msg: str | None
  master_paths: dict      # { '1:1': 'path/to/master-1x1.jpg', 'long': ..., ... }
  derived_paths: dict     # { 'douyin/main_1080.jpg': 'path/...', ... }

PlatformOutputCopy:        # 电商字段，per (SKU, platform, generator)
  id, sku_id
  platform: enum          # douyin|shipinhao|taobao|xiaohongshu
  generated_by: enum      # gpt-5|claude
  title, subtitle
  selling_points: list[str]
  description_md: str
  category_path: str
  keywords: list[str]
  platform_specific: jsonb # 各平台特殊字段（小红书 hashtags、淘宝 attributes）
  selected: bool          # 用户最终选中的版本
```

### 5.2 状态机

**SKU 状态**：
```
   ┌─ 用户创建 ─→ draft (草稿，未上传图)
   │              ↓ 上传图
   ↓
ready ─ 点开始处理 ─→ running ─ 全成功 ─→ done
   ↑                       │
   │                       └ 部分失败 ─→ error
   └─ 追加新图 ←──────── done/error
```

**SourceImage 状态**：
```
pending → cutting → generating → composing → done
                ↘            ↘            ↘
                  failed       failed       failed
                    ↑ 用户手动重试 ↑
```

### 5.3 增量处理
- "开始处理"只 process `pending` + `failed` 的 image，已 `done` 的不动（保留旧 outputs）
- SKU `done` 后追加图 → SKU 切回 `ready`，新图 `pending`，旧图 `done` 保持
- 删除原图：`pending` 直接删；`done` 同时清 master + derived 文件
- **追加原图的可见时机**：所有非 `running` 状态都可追加（draft / ready / done / error）。`running` 时不允许，避免任务队列扰动；V1.1+ 实现"加入运行中队列"后放开

## 6. 数据流（单 SKU 处理）

```
用户点 "开始处理"
    ↓
FastAPI POST /api/skus/{id}/process
    ↓
为每张 pending/failed image 创建 Celery 任务
    ↓ (异步)
Worker 拉任务（每张 image 一个）：
  1. 白底检测（Pillow 边缘像素方差 < 阈值 → 判定白底）
     - 白底 → 跳过抠图
     - 否则 → rembg 抠图（CPU），失败时 ComfyUI SAM workflow 兜底
  2. 调 ComfyUI workflow `generate_master.json`
     - 输入：cutout RGBA + scene config（prompt / neg / ref_img / weight / model）
     - 输出：5 张 master（一次 workflow 跑多个 KSampler 节点）
  3. 拉 master 回 mac
  4. Pillow 派生：对每平台每尺寸，从对应 master 裁剪/缩放/补白
  5. 调 LLM Provider 生成电商字段（GPT-5 + Claude 双路并发）
  6. 详情页拼图：用 selling_points 套模板叠字 → outputs/{platform}/detail_*.jpg
  7. 写 SQLite + 落文件
  8. SSE 推送 image-progress 事件到前端
    ↓
全部 image 完成 → SKU.status = done（或 error）→ SSE 推送 sku-status 事件
```

## 7. 电商字段生成

### 7.1 字段 Schema（每平台）
| 字段 | 抖店 | 视频号 | 淘宝/天猫 | 小红书 |
|---|---|---|---|---|
| 标题 | ≤60 字 | ≤30 字 | ≤30 字 | 笔记标题 ≤20 字 |
| 副标题 / 卖点短语 | ✓ | ✓ | ✓ | — |
| 卖点列表（3-5） | ✓ | ✓ | ✓ | ✓ |
| 描述 / 详情段落（markdown） | ✓ | ✓ | ✓ | 笔记正文 |
| 推荐类目路径 | ✓ | ✓ | ✓ | — |
| 关键词 / 搜索词 | 5-10 | 5-10 | 5-10 | — |
| Hashtag | — | — | — | 5-10 个 |
| 30s 短视频脚本 | ✓ | ✓ | — | ✓ |
| 商品属性（淘宝 SKU 规格） | — | — | ✓ | — |

### 7.2 生成方式
- 单次 LLM 调用（结构化 JSON 输出），输入：
  - VLM 识别结果（GPT-4o vision，输出商品类目、特征、颜色、材质）
  - 场景模板信息（关联场景类别）
  - 用户填写的备注（可选）
  - 平台 schema（要求字段、字数限制）
- 两路并发：GPT-5 + Claude，前端展示双份让用户挑（在 SKU 详情页底部 Tab）
- LLMProvider 抽象：方便后期换/加 provider

### 7.3 详情页拼图叠字
- 主图保持纯场景图，无字
- 详情页拼图（750w 长图派生）需要叠字：
  - selling_points 进入预设布局（位置、字号、颜色 in JSON 模板）
  - Pillow + 思源黑体/苹方 渲染
  - 输出到 `outputs/{platform}/detail_*.jpg`

## 8. 文件系统布局

```
~/img2ec/projects/                  # 用户配置的根目录（设置可改）
├── default/                        # 项目目录 = slug(项目名)
│   ├── _project.json               # 项目元数据（DB 镜像）
│   ├── _scenes/                    # 场景模板的参考图
│   │   ├── sc-marble.png
│   │   └── sc-wood.png
│   ├── 蓝色保温杯-500ml/           # SKU 目录 = slug(SKU 名)
│   │   ├── source/                 # 原图（用户上传）
│   │   │   ├── front.jpg
│   │   │   └── side.jpg
│   │   ├── cutout/                 # 抠图结果
│   │   │   ├── front.png
│   │   │   └── side.png
│   │   ├── master/                 # AI 生成的 5 张 master / 原图
│   │   │   ├── front-1x1.jpg
│   │   │   ├── front-long.jpg
│   │   │   ├── front-3x4.jpg
│   │   │   ├── front-9x16.jpg
│   │   │   ├── front-16x9.jpg
│   │   │   └── side-... (同上 5 张)
│   │   ├── outputs/                # 派生平台输出
│   │   │   ├── douyin/
│   │   │   │   ├── front-main-1080x1080.jpg
│   │   │   │   ├── front-detail-750x1500.jpg
│   │   │   │   ├── front-cover-3x4.jpg
│   │   │   │   └── front-cover-9x16.jpg
│   │   │   ├── shipinhao/
│   │   │   ├── taobao/
│   │   │   └── xiaohongshu/
│   │   ├── copy.json               # 4 平台电商字段（含 GPT-5 与 Claude 两版）
│   │   └── _sku.json               # SKU 元数据 + 状态镜像
│   └── 真皮男包/
└── 双11促销/
```

`_project.json` / `_sku.json` 是 SQLite 状态的镜像（写两次），方便：
- 用户在 Finder 直接看到状态
- 后期接 watchdog 反向驱动（V1.1+）
- 备份与迁移

## 9. 模块清单

### 9.1 后端（FastAPI 工程）
```
img2ec_backend/
├── api/
│   ├── projects.py        # /api/projects CRUD
│   ├── scenes.py          # /api/scenes CRUD + import-defaults
│   ├── skus.py            # /api/skus CRUD + /process /add-images /retry
│   ├── outputs.py         # /api/skus/{id}/download (zip 流式)
│   │                      # /api/projects/{id}/download-all
│   ├── fs.py              # /api/fs/reveal (在 Finder 中显示)
│   ├── events.py          # /api/skus/{id}/events (SSE，前端用)
│   └── webhooks.py        # /api/webhooks CRUD (订阅管理 + dead_letter 查询)
├── core/
│   ├── pipeline.py        # 编排：bg_detect → cut → master_gen → derive → copy_gen → compose
│   ├── bg_detect.py       # 白底检测（Pillow 边缘方差）
│   ├── cutout.py          # rembg + SAM 兜底
│   ├── master_gen.py      # 调 ComfyUI 生 5 master
│   ├── derive.py          # Pillow 派生：master → platform sizes
│   ├── copy_gen.py        # 调 LLM 生电商字段（双路并发）
│   └── compose.py         # 详情页拼图叠字（Pillow + 字体）
├── infra/
│   ├── comfy_client.py    # ComfyUI HTTP client
│   ├── llm_provider.py    # Abstract + GPT5/Claude impls
│   ├── input_source.py    # Abstract: WebUploadSource (V1) / FileSystemWatchSource (V2)
│   ├── fs_layout.py       # 路径生成、zip 打包
│   ├── reveal.py          # subprocess.run(['open', '-R', path]) macOS / explorer.exe Windows
│   └── event_bus.py       # 事件发射 + webhook 投递 + 退避重试 + dead_letter
├── models/                # SQLAlchemy ORM
├── tasks/                 # Celery tasks
├── seeds/
│   └── default_scenes.py  # 16 个默认场景定义
└── main.py
```

### 9.2 前端（Next.js）
```
img2ec_frontend/
├── app/
│   ├── projects/page.tsx                          # 项目列表
│   ├── projects/[pid]/skus/page.tsx               # SKU 列表（默认 Tab）
│   ├── projects/[pid]/scenes/page.tsx             # 场景库（第二 Tab）
│   └── projects/[pid]/skus/[sid]/page.tsx         # SKU 详情
├── components/
│   ├── ProjectCard.tsx
│   ├── SkuRow.tsx
│   ├── SceneCard.tsx
│   ├── SceneEditor.tsx           # 模态：编辑场景
│   ├── NewSkuModal.tsx           # 模态：新建 SKU
│   ├── AddImagesModal.tsx        # 模态：追加原图
│   ├── MasterGallery.tsx         # 5 张 master 卡片
│   ├── DerivedTable.tsx          # 平台派生表
│   ├── BizFieldsTabs.tsx         # 4 平台字段 Tab + 复制 + 字数
│   └── PathBar.tsx               # 路径 + Finder/Copy 按钮
├── lib/api.ts
└── lib/sse.ts
```

### 9.3 ComfyUI workflow（gpu box 配置）
- `workflows/generate_master.json` — 接收 cutout + scene config，输出 5 张 master
- `workflows/sam_cutout.json` — rembg 失败时兜底
- 模型权重需预装：Flux dev FP8、SDXL Base、IPAdapter Plus、SAM ViT-B、ControlNet Canny

## 10. 错误处理

### 10.1 失败粒度
- 失败定位到 SourceImage 级，不影响同 SKU 其它图
- SKU.status 由所有 image 状态聚合：任一 failed → SKU.status = error
- 重试两个粒度：单图重试（image 行的"重试"）/ SKU 级（"重试失败项"）

### 10.2 常见失败与策略
| 场景 | 策略 |
|---|---|
| rembg 抠图失败（边缘破碎） | 自动调 ComfyUI SAM workflow 兜底；仍失败 → image.failed |
| ComfyUI HTTP 超时 / 连接失败 | Celery 自动重试 3 次（退避 30s/2m/5m），仍失败 → image.failed |
| GPU OOM | image.failed，err_msg = "GPU OOM"；用户可降模型（Flux→SDXL→Schnell）后重试 |
| LLM API 错误 / 限流 | 退避重试 2 次；仍失败 → 字段生成跳过，可手动重试，**不阻塞图片输出** |
| 单 platform 派生失败 | 该平台该尺寸 image.failed_platforms 记录；其它平台正常输出 |
| 网络问题导致 ComfyUI 不可达 | 整 SKU 暂停（pending），UI 显示"等待 GPU 上线"；用户可手动恢复 |

### 10.3 不重试
- 用户主动取消的任务不重试
- 同一 image 失败超过 3 次自动停止（用户手动介入）

## 11. 持久化与可恢复性

### 11.1 真相源
**SQLite 是唯一权威**：所有 status / progress / paths 从 DB 读。`_sku.json` / `_project.json` 是镜像，仅供查看与外部工具使用。

### 11.2 进程重启恢复
- **FastAPI 重启**：从 SQLite 拉所有 SKU 当前状态，正常服务
- **Celery worker 重启**：Redis 队列未消费的任务自动重新派发；`acks_late=True` 确保进行中任务在 worker 崩溃时由其它 worker 接手
- **mac 整机断电**：上电 → docker-compose up → 所有未完成 jobs 由 Celery 重试（按 retry policy）

### 11.3 浏览器状态
浏览器是纯 viewer：
- 路由 `/projects/{pid}/skus/{sid}` 进入 SKU 详情
- 拉 `GET /api/skus/{sid}` 拿 snapshot（DB 完整状态）
- 订阅 `GET /api/skus/{sid}/events` (SSE) 拿增量推送
- **刷新无感知**：错过的事件靠 snapshot 兜底，不会丢状态

## 12. 事件与 n8n 集成

### 12.1 设计动机
核心 pipeline 固定（保速度/稳定/可重试），但用户对"图做完之后干什么"的诉求多变：上传 OSS、通知飞书、推到 ERP、自定义审核等。EventBus 在关键节点发 webhook，外部工具（n8n / 任何 webhook 接收器）订阅做自定义后处理。**核心不绑定 n8n，n8n 只是最常用的消费者**。

### 12.2 事件清单（V1 范围）

| 事件名 | 触发时机 | Payload 关键字段 |
|---|---|---|
| `project.created` | 新建项目 | `project_id, name, root_path` |
| `sku.created` | 新建 SKU | `sku_id, project_id, name, image_count` |
| `sku.processing.started` | 用户点开始处理 | `sku_id, target_image_count` |
| `image.cutout.done` | 单图抠图完成 | `sku_id, image_id, cutout_path` |
| `image.master.done` | 单图 5 张 master 都生完 | `sku_id, image_id, master_paths` |
| `image.derived.done` | 单图所有派生输出落盘 | `sku_id, image_id, derived_paths` |
| `image.failed` | 单图处理失败 | `sku_id, image_id, stage, err_msg` |
| `sku.done` | SKU 全部图完成 | `sku_id, project_id, output_dir, copy_path` |
| `sku.failed` | SKU 部分失败 | `sku_id, failed_count, total_count` |

### 12.3 事件 Payload 通用结构
```json
{
  "event": "sku.done",
  "ts": 1740000000,
  "version": "1",
  "data": { /* 事件特定字段 */ }
}
```

`version` 用于将来字段演进（后向兼容时不变，破坏性变更时升级）。

### 12.4 EventBus 实现
- **异步投递**：内存队列 + 独立 worker，不阻塞主 pipeline
- **订阅配置**：每事件可有多个订阅 URL；通过设置页 UI 或 `POST /api/webhooks` 管理
- **失败重试**：指数退避 3 次（30s / 2min / 10min）
- **死信队列**：超过 3 次失败 → 写入 `dead_letter` 表 + UI 通知 + 可手动重投
- **签名校验**（可选）：HMAC-SHA256 用订阅时配置的 secret 签 payload，n8n 侧验证
- **模块**：`infra/event_bus.py`（发射 + 投递）+ `api/webhooks.py`（订阅管理 + dead_letter API）

### 12.5 数据模型扩充
```python
WebhookSubscription:
  id, event_pattern: str        # "sku.done" | "image.*" | "*"（通配符）
  url: str
  secret: str | None            # HMAC 签名密钥
  enabled: bool
  retry_policy: jsonb           # 默认 3 次退避
  created_at, updated_at

WebhookDelivery:
  id, subscription_id, event_id
  status: enum                  # pending|success|failed|dead
  attempt_count: int
  last_error: str
  next_retry_at: datetime | None
  payload: jsonb
  created_at
```

### 12.6 n8n 接入示例

**示例 A：sku 完成后自动上传 OSS + 飞书通知**
1. n8n 创建 webhook 节点：`POST /webhook/img2ec/sku-done`
2. img2ec 设置页订阅 `sku.done` → 这个 URL
3. n8n 工作流：webhook → 读 `output_dir` 目录 → 阿里云 OSS 上传 → 飞书消息（含上传后的链接）

**示例 B：n8n 当输入源**
1. n8n 监听共享文件夹（Dropbox/邮件附件/钉钉消息）
2. 收到新图 → 调 `POST /api/skus`（img2ec 标准 API）创建 SKU
3. 上传图 → POST `/api/skus/{id}/process` → img2ec 走标准流程

**示例 C：失败时通知 + ERP 同步**
- 订阅 `sku.failed` → 发飞书告警群
- 订阅 `sku.done` → 调用公司 ERP 系统的"上架"接口，自动新增商品记录

更多 cookbook 在实现阶段编写到 `docs/n8n-recipes.md`。

### 12.7 不在 EventBus 范围内的能力
明确边界，避免范围蔓延：
- **流程编排**：核心 pipeline 顺序固定，不接受 n8n 改变 stage 顺序（要灵活性走 V1.1+ 的插件化 pipeline）
- **状态权威**：SQLite 仍是唯一真相源，n8n 不能改 SKU/Image 状态
- **重试控制**：失败重试由 Celery + img2ec 决定，n8n 收到的是只读事件流
- **同步调用**：所有 webhook 异步发出，img2ec 不等响应；要同步阻塞型调用走 V1.1+

## 13. UI / UX

### 12.1 页面层级
1. 项目列表（首页 `/projects`）
2. 项目内：SKU 列表（默认 Tab）/ 场景库（第二 Tab）
3. SKU 详情（嵌套路由）
4. 模态：新建项目 / 新建 SKU / 编辑场景 / 更换场景 / 追加原图

### 12.2 关键 UX 决策
- **路径透出**：项目列表顶部和 SKU 详情页都显示本地路径，配 "在 Finder 中显示" / "复制路径" 按钮 — 本地 Web 应用打通"网页 ↔ 文件系统"
- **场景库分类筛选**：16 个默认场景按 category 分组，filter pill 筛选
- **状态显式**：SKU 行用 pill 显示状态，详情页每张原图独立 progress bar
- **追加原图**：所有非 running 状态都可追加；done → ready 的过渡保留旧 outputs 不重做
- **一键下载**：单 SKU 完成 → "⬇ 一键下载 zip"（打包 outputs/）；项目级 → "⬇ 下载已完成 (N)" 批量打包

### 12.3 关键页面
- **项目列表**：项目卡片（含 SKU/场景计数）+ "+ 新建项目"
- **SKU 列表**：项目目录条（路径 + Finder/Copy + 全部下载）+ SKU 行（缩略图、状态、行动按钮）+ "+ 新建 SKU"
- **场景库**：信息面板 + 品类筛选 + 4 列场景卡片 + "+ 新建场景"
- **SKU 详情**：
  - Top 行：SKU 名 + 状态 pill + 主操作（开始处理 / 暂停 / 下载 / 重试）+ 删除
  - 第二行：SKU 路径 + Finder / Copy 按钮
  - 左：原图列表（每张状态 + 进度）+ "+ 追加原图" + 完成后 master gallery + 平台派生表
  - 右：场景配置卡 + 输出策略说明（标注 GPU 节省）+ 输出平台 + 文案设置
  - 底（done 后）：商品字段 4 平台 Tab × 字段（带字数 + 复制 + 双 LLM 切换）

## 14. 测试策略

### 13.1 单元测试
- `bg_detect`：用一组已知白底/非白底图测准确率（≥95%）
- `derive`：每平台每尺寸固定输入，对比期望像素 hash
- `compose`：详情页拼图叠字定位测试（用固定字体 + 固定文字）
- `llm_provider`：mock OpenAI/Anthropic SDK，验证调用 schema、字段长度截断

### 13.2 集成测试
- E2E SKU 处理：mock ComfyUI 返回固定图，验证整个 pipeline 跑通，状态机正确
- Celery 任务恢复：杀 worker 进程，验证任务被其它 worker 重新拉起完成
- SSE 事件流：发起处理，验证客户端能收到完整状态变化、断线重连后能从 snapshot 恢复

### 13.3 验收测试
- 跑 5 个真实 SKU（覆盖白底+拍照、单图+多图、不同品类）
- 检查输出目录结构、各平台尺寸像素正确、电商字段完整且不超字
- 浏览器刷新 / 关闭 / 重连场景手测

## 15. 实施分阶段

### Phase 1（MVP）— 2 周
- 项目/SKU/场景模板 CRUD
- 单 SKU 单图处理 pipeline（白底检测 → rembg → ComfyUI 1 master → Pillow 派生 4 平台 1:1 主图）
- Web UI 基础（项目列表、SKU 列表、SKU 详情）
- 路径显示 + Finder 集成
- SQLite 状态持久化
- 内置 **1 个默认场景**（大理石台·暖光），跑通 E2E

### Phase 2 — 1 周
- 完整 5 master + 15 派生
- 详情页拼图叠字
- LLM 字段生成（4 平台 schema，GPT-5 + Claude 双路）
- 一键下载 zip + 批量下载
- **扩充默认场景到 16 个**（按品类分组）

### Phase 3 — 1.5 周
- Celery 任务队列 + acks_late + 失败退避重试
- SSE 事件流 + 浏览器刷新无感
- 增量处理（追加原图后只跑新增）
- 错误处理细化（OOM 降级、SAM 兜底）
- **EventBus + webhook 订阅**（v1 事件清单全量）+ n8n cookbook 文档
- 设置页 v1（webhook 订阅管理 + dead_letter 查看 + 项目根目录）

### Phase 4（V1.1+）
- FileSystemWatchSource（用户在 Finder 直接组织 SKU 文件夹）
- 单图覆盖场景（同 SKU 不同图用不同模板）
- 处理中追加原图（加入运行中队列）
- 模型权重切换 UI（Flux ↔ SDXL ↔ Flux schnell）
- 设置页 v2（API Key、默认底模、白底检测阈值）
- 模特上身 / 试衣（针对服饰品类）
- 场景包导入/导出（社区/团队共享场景库）
- **插件化 pipeline（Level 2 灵活性）**：stage 抽成插件，允许跳过/换实现/调顺序
- **场景模板绑定 ComfyUI workflow JSON**：高级用户自定义生图流程（V1 默认共用一个 workflow）
- 不做：把核心 pipeline 完全搬到 n8n 编排（Level 3，速度/调试/状态一致性代价过高）

## 16. 风险与权衡

| 风险 | 缓解 |
|---|---|
| ComfyUI workflow 调试复杂 | workflow 单文件版本化在 git，附 README 说明节点连接；用 `workflows/test_inputs/` 跑回归 |
| GPU box 网络延迟 | 局域网内可接受；远程时用 Tailscale；大图传输 chunked + gzip |
| LLM 字段超字数 | prompt 强约束 + 后处理截断 + UI 标红显示；提供"重新生成此字段"按钮 |
| Flux FP8 与 SDXL 风格不一 | 场景模板绑定 base_model；切模型时自动重新生 master |
| 16 个默认场景不够 | 用户可自建；后期发布"场景包"扩展机制（导入 JSON） |
| 商品被场景吞掉（商品太小） | IPAdapter 权重 + ControlNet edge 锁住商品轮廓；用户可调权重；预览时人工确认 |
| Codex CLI 与 Claude 写出代码风格不一 | 统一在 spec 里规定模块边界；codex-worker 写样板，CC 写关键逻辑 |
| webhook 订阅指向不可达 URL（用户配错） | 退避 3 次后写 dead_letter + UI 红点提示；不阻塞 pipeline |
| n8n 工作流死循环（n8n 调 img2ec 又触发 img2ec 发 webhook 给 n8n） | webhook payload 加 `_source` 字段；n8n 推荐做幂等检查；img2ec 自身不引入循环检测（用户层职责） |
| 事件 schema 演进破坏既有 n8n 工作流 | payload 带 `version` 字段；破坏性变更升版本，并行支持新旧版至少一个 phase |
