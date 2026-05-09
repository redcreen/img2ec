# img2ec

国内电商图自动化生成工具：上传商品图，自动生成抖店 / 视频号 / 淘宝 / 小红书 各平台所需尺寸的电商图。

## 它在做什么

- **智能抠图**：自动检测白底 vs 拍照，按需 rembg 抠图
- **AI 场景生成**：基于场景模板，调本地 GPU 上的 ComfyUI（Flux / SDXL）生成商品场景图
- **平台尺寸派生**：1 张 master → 多平台多尺寸（共 aspect ratio 共用一次生成，省 67% GPU）
- **本地 Web 应用**：浏览器关闭/刷新不影响后台处理；输出落本地文件系统，可在 Finder 直接看到
- **场景模板管理**：内置国内电商常用场景，可自建/编辑

## 架构

- **mac 业务层**：FastAPI + Celery + Redis + SQLite + Next.js
- **gpu box 推理层**：ComfyUI（Windows，RTX 4080 SUPER）暴露 HTTP API
- **云端 LLM**（Phase 2+）：OpenAI + Anthropic 双路生电商字段
- **n8n 集成**（Phase 3+）：webhook 事件钩子供用户自定义后处理流程

## 文档

- [设计文档](docs/superpowers/specs/2026-05-09-img2ec-design.md) — 完整架构、数据模型、状态机、错误处理
- [Phase 1 MVP 实施计划](docs/superpowers/plans/2026-05-09-img2ec-phase1-mvp.md) — 17 个 TDD 任务
- ComfyUI 配置文档（待补充）

## 状态

🚧 早期开发中（Phase 1 MVP 实施阶段）
