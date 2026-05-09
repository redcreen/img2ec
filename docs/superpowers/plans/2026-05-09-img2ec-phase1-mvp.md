# img2ec Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single SKU 端到端跑通：用户在 Web UI 创建项目和 SKU，上传 1 张原图，选用 1 个内置场景"大理石台·暖光"，触发处理流水线（白底检测 → rembg → ComfyUI 生 1 master → Pillow 派生 4 平台 1:1 主图），结果落本地文件系统并能在 Finder 中显示，可下载 zip。

**Architecture:** 路线 C — FastAPI 业务编排 + Celery 异步执行 + Redis 队列 + SQLite 状态，ComfyUI 跑在 gpu box 远程暴露 HTTP API；Next.js 前端纯查看器。MVP 不实现 LLM 字段生成、详情页拼图、5-master 全量、增量处理、EventBus（Phase 2/3 加）。

**Tech Stack:**
- 后端：Python 3.11、FastAPI、SQLAlchemy 2.0、Alembic、Celery 5、Redis 7、Pillow、rembg、httpx、Pydantic v2
- 前端：Next.js 14（App Router）、TypeScript 5、Tailwind CSS、SWR
- 推理：ComfyUI（gpu box 已部署，本计划只调其 HTTP API）
- 测试：pytest、pytest-asyncio、Vitest
- 容器：docker-compose（Redis 用容器）；Python/Node 进程在宿主机跑

**Spec reference:** `docs/superpowers/specs/2026-05-09-img2ec-design.md`

---

## File Structure

```
img2ec/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── img2ec/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app 入口
│   │   ├── config.py                # pydantic-settings：DB URL、ComfyUI URL、root path
│   │   ├── db.py                    # SQLAlchemy session
│   │   ├── celery_app.py            # Celery 初始化
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Declarative base
│   │   │   ├── project.py
│   │   │   ├── scene.py
│   │   │   ├── sku.py
│   │   │   └── source_image.py
│   │   ├── schemas/                 # Pydantic API schemas
│   │   │   ├── project.py
│   │   │   ├── scene.py
│   │   │   ├── sku.py
│   │   │   └── source_image.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py
│   │   │   ├── scenes.py
│   │   │   ├── skus.py
│   │   │   ├── outputs.py           # zip 下载
│   │   │   └── fs.py                # /api/fs/reveal
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py          # 编排：bg_detect → cutout → master_gen → derive
│   │   │   ├── bg_detect.py
│   │   │   ├── cutout.py
│   │   │   ├── master_gen.py
│   │   │   └── derive.py
│   │   ├── infra/
│   │   │   ├── __init__.py
│   │   │   ├── comfy_client.py
│   │   │   ├── fs_layout.py         # 路径生成、slug
│   │   │   └── reveal.py            # subprocess open -R
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   └── pipeline_tasks.py    # Celery tasks
│   │   └── seeds/
│   │       └── default_scenes.py    # 1 个默认场景
│   ├── workflows/
│   │   └── generate_master_1x1.json # ComfyUI workflow
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── fixtures/
│   │   │   ├── white_bg.jpg
│   │   │   └── photo_bg.jpg
│   │   ├── test_infra/
│   │   ├── test_core/
│   │   └── test_api/
│   └── docker-compose.yml           # Redis 容器
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── next.config.mjs
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                 # 重定向到 /projects
    │   ├── globals.css
    │   ├── providers.tsx            # SWRConfig
    │   └── projects/
    │       ├── page.tsx             # 项目列表
    │       └── [pid]/
    │           ├── layout.tsx       # 顶栏 + Tab
    │           ├── skus/
    │           │   ├── page.tsx     # SKU 列表
    │           │   └── [sid]/
    │           │       └── page.tsx # SKU 详情
    │           └── scenes/
    │               └── page.tsx     # 场景库
    ├── components/
    │   ├── PathBar.tsx
    │   ├── NewProjectModal.tsx
    │   ├── NewSkuModal.tsx
    │   ├── SceneCard.tsx
    │   ├── SkuRow.tsx
    │   └── StatusPill.tsx
    ├── lib/
    │   ├── api.ts                   # fetch 封装
    │   └── types.ts                 # shared TS 类型
    └── tests/
        └── lib/
            └── api.test.ts
```

---

## Task Map (vs spec sections)

| Task | 实现 spec 哪一部分 |
|---|---|
| 1 项目初始化 | §2.2 拓扑（mac 业务进程） |
| 2 数据模型 + Alembic | §5.1 Project/Scene/SKU/SourceImage |
| 3 默认场景种子 | §4.3 MVP 场景 |
| 4 fs_layout + reveal | §8 文件系统、§12.2 Finder 集成（spec §13.2） |
| 5 bg_detect | §6 数据流 step 1 |
| 6 cutout (rembg) | §6 数据流 step 1（rembg） |
| 7 ComfyUI client + workflow | §6 step 2 |
| 8 master_gen | §6 step 2-3 |
| 9 derive (Pillow 派生 4 平台) | §3.3 派生表 |
| 10 pipeline + Celery task | §6 编排 |
| 11 API: Projects + Scenes | §9.1 |
| 12 API: SKUs + upload + process | §9.1 + §6 |
| 13 前端：scaffold + 项目列表 | §13.3 |
| 14 前端：场景库 + 新建场景 | §13.3 |
| 15 前端：SKU 列表 + 路径栏 + 新建 SKU | §13.3 |
| 16 前端：SKU 详情 + 处理 + 下载 | §13.3 |
| 17 E2E + smoke 验收 | §14.3 |

---

## Task 1: 项目初始化与脚手架

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/img2ec/__init__.py`
- Create: `backend/img2ec/main.py`
- Create: `backend/img2ec/config.py`
- Create: `backend/docker-compose.yml`
- Create: `backend/tests/conftest.py`
- Create: `frontend/package.json`
- Create: `frontend/next.config.mjs`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd /Users/redcreen/Project/img2ec
git init
```

- [ ] **Step 2: 写 .gitignore**

```
__pycache__/
*.pyc
.venv/
node_modules/
.next/
*.db
*.db-journal
.env
.env.local
.DS_Store
.superpowers/
backend/storage/
projects/
.pytest_cache/
.ruff_cache/
dist/
build/
```

- [ ] **Step 3: 写后端 `backend/pyproject.toml`**

```toml
[project]
name = "img2ec"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "celery>=5.4",
    "redis>=5.2",
    "httpx>=0.27",
    "pillow>=11.0",
    "rembg>=2.0.59",
    "python-multipart>=0.0.12",
    "websockets>=13.1",
    "sse-starlette>=2.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: 写 `backend/img2ec/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: 写 `backend/img2ec/config.py`**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="IMG2EC_")

    db_url: str = "sqlite:///./img2ec.db"
    redis_url: str = "redis://localhost:6379/0"
    comfy_url: str = "http://gpu:8188"
    comfy_timeout: int = 300

    root_path: Path = Path.home() / "img2ec" / "projects"

    cors_origins: list[str] = ["http://localhost:3000"]


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: 写 `backend/img2ec/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from img2ec.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="img2ec", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 7: 写 `backend/docker-compose.yml`**

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
```

- [ ] **Step 8: 写 `backend/tests/conftest.py`**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from img2ec.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 9: 写第一个测试 `backend/tests/test_api/test_health.py`**

```python
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 10: 安装依赖并跑测试**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_api/test_health.py -v
```

Expected: PASS

- [ ] **Step 11: 启动 Redis**

```bash
docker compose up -d redis
docker compose ps
```

Expected: redis-1 running on port 6379

- [ ] **Step 12: 写前端 `frontend/package.json`**

```json
{
  "name": "img2ec-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "swr": "^2.2.5"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.6.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 13: 写前端配置文件**

`frontend/next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
    ];
  },
};
export default nextConfig;
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "incremental": true,
    "noEmit": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "paths": { "@/*": ["./*"] },
    "plugins": [{ "name": "next" }]
  },
  "include": ["**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`frontend/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

`frontend/postcss.config.mjs`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 14: 写前端入口 `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "img2ec" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen">{children}</body>
    </html>
  );
}
```

- [ ] **Step 15: 写 `frontend/app/page.tsx` 和 `globals.css`**

`frontend/app/page.tsx`:
```tsx
import { redirect } from "next/navigation";
export default function Home() { redirect("/projects"); }
```

`frontend/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`frontend/app/projects/page.tsx`（占位）:
```tsx
export default function Projects() {
  return <main className="p-6"><h1 className="text-xl">Projects (placeholder)</h1></main>;
}
```

- [ ] **Step 16: 安装前端依赖并启动**

```bash
cd frontend
npm install
npm run dev
```

Expected: 打开 `http://localhost:3000` 自动跳到 `/projects`，看到 "Projects (placeholder)"

- [ ] **Step 17: Commit**

```bash
git add -A
git commit -m "chore: scaffold backend (FastAPI) and frontend (Next.js) for Phase 1 MVP"
```

---

## Task 2: 数据库模型与 Alembic 迁移

**Files:**
- Create: `backend/img2ec/db.py`
- Create: `backend/img2ec/models/base.py`
- Create: `backend/img2ec/models/__init__.py`
- Create: `backend/img2ec/models/project.py`
- Create: `backend/img2ec/models/scene.py`
- Create: `backend/img2ec/models/sku.py`
- Create: `backend/img2ec/models/source_image.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/tests/test_models/test_orm.py`

- [ ] **Step 1: 写 `backend/img2ec/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from img2ec.config import get_settings

_settings = get_settings()
engine = create_engine(_settings.db_url, echo=False, connect_args={"check_same_thread": False} if _settings.db_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: 写 `backend/img2ec/models/base.py`**

```python
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 3: 写 `backend/img2ec/models/project.py`**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    desc: Mapped[str] = mapped_column(String(500), default="")
    root_path: Mapped[str] = mapped_column(String(500), nullable=False)

    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    skus = relationship("SKU", back_populates="project", cascade="all, delete-orphan")
```

- [ ] **Step 4: 写 `backend/img2ec/models/scene.py`**

```python
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="自定义")
    desc: Mapped[str] = mapped_column(String(500), default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    ref_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_adapter_weight: Mapped[int] = mapped_column(Integer, default=60)
    base_model: Mapped[str] = mapped_column(String(60), default="flux-dev-fp8")

    project = relationship("Project", back_populates="scenes")
```

- [ ] **Step 5: 写 `backend/img2ec/models/sku.py`**

```python
from enum import Enum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class SKUStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SKU(Base, TimestampMixin):
    __tablename__ = "skus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SKUStatus.DRAFT.value, nullable=False)

    project = relationship("Project", back_populates="skus")
    scene = relationship("Scene")
    images = relationship("SourceImage", back_populates="sku", cascade="all, delete-orphan")
```

- [ ] **Step 6: 写 `backend/img2ec/models/source_image.py`**

```python
from enum import Enum
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from img2ec.models.base import Base, TimestampMixin


class ImageStatus(str, Enum):
    PENDING = "pending"
    CUTTING = "cutting"
    GENERATING = "generating"
    COMPOSING = "composing"
    DONE = "done"
    FAILED = "failed"


class SourceImage(Base, TimestampMixin):
    __tablename__ = "source_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    src_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ImageStatus.PENDING.value, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    master_paths: Mapped[dict] = mapped_column(JSON, default=dict)
    derived_paths: Mapped[dict] = mapped_column(JSON, default=dict)

    sku = relationship("SKU", back_populates="images")
```

- [ ] **Step 7: 写 `backend/img2ec/models/__init__.py`**

```python
from img2ec.models.base import Base
from img2ec.models.project import Project
from img2ec.models.scene import Scene
from img2ec.models.sku import SKU, SKUStatus
from img2ec.models.source_image import SourceImage, ImageStatus

__all__ = ["Base", "Project", "Scene", "SKU", "SKUStatus", "SourceImage", "ImageStatus"]
```

- [ ] **Step 8: 初始化 Alembic**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 9: 改 `backend/alembic.ini` sqlalchemy.url 行**

```ini
sqlalchemy.url = sqlite:///./img2ec.db
```

- [ ] **Step 10: 改 `backend/alembic/env.py`**

`alembic init` 生成的 `env.py` 顶部 import 区域加：
```python
from img2ec.config import get_settings
from img2ec.models import Base
```

找到 `config = context.config` 这一行，紧接其后加：
```python
config.set_main_option("sqlalchemy.url", get_settings().db_url)
```

找到 `target_metadata = None` 这一行，改为：
```python
target_metadata = Base.metadata
```

- [ ] **Step 11: 生成首次迁移**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: `img2ec.db` 文件创建，含 4 张表

- [ ] **Step 12: 写测试 `backend/tests/test_models/test_orm.py`**

```python
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from img2ec.models import Base, Project, Scene, SKU, SourceImage, SKUStatus, ImageStatus


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_project_with_scene_and_sku(session):
    p = Project(id=str(uuid.uuid4()), name="default", desc="d", root_path="/tmp/p")
    sc = Scene(
        id=str(uuid.uuid4()), project_id=p.id, name="大理石台·暖光",
        category="美妆/食品", prompt="on white marble, warm light",
    )
    sku = SKU(id=str(uuid.uuid4()), project_id=p.id, scene_id=sc.id, name="测试 SKU")
    img = SourceImage(id=str(uuid.uuid4()), sku_id=sku.id, name="front.jpg", src_path="/tmp/p/front.jpg")
    session.add_all([p, sc, sku, img])
    session.commit()

    fetched = session.query(Project).first()
    assert fetched.name == "default"
    assert len(fetched.scenes) == 1
    assert len(fetched.skus) == 1
    assert fetched.skus[0].images[0].status == ImageStatus.PENDING.value


def test_cascade_delete(session):
    p = Project(id="p1", name="default", root_path="/tmp/p1")
    sku = SKU(id="s1", project_id="p1", name="测试")
    img = SourceImage(id="i1", sku_id="s1", name="a.jpg", src_path="/tmp/a.jpg")
    session.add_all([p, sku, img])
    session.commit()

    session.delete(p)
    session.commit()

    assert session.query(SKU).count() == 0
    assert session.query(SourceImage).count() == 0
```

- [ ] **Step 13: 跑测试**

```bash
cd backend
pytest tests/test_models -v
```

Expected: 2 passed

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat(db): add Project/Scene/SKU/SourceImage models and Alembic migration"
```

---

## Task 3: 默认场景种子

**Files:**
- Create: `backend/img2ec/seeds/__init__.py`
- Create: `backend/img2ec/seeds/default_scenes.py`
- Create: `backend/tests/test_seeds/test_default_scenes.py`

- [ ] **Step 1: 写 `backend/img2ec/seeds/default_scenes.py`**

```python
"""MVP Phase 1：仅 1 个默认场景。Phase 2 再扩充到 16 个。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSeed:
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    ip_adapter_weight: int = 60
    base_model: str = "flux-dev-fp8"


DEFAULT_SCENES: list[SceneSeed] = [
    SceneSeed(
        name="大理石台·暖光",
        category="美妆/食品",
        desc="美妆护肤、轻食、礼品类首选；通用度高，跨品类适配",
        prompt=(
            "product on a white marble surface, warm soft window light from the left, "
            "45-degree camera angle, premium product photography, shallow depth of field, "
            "minimal composition, natural shadows"
        ),
        negative_prompt="cluttered, harsh light, oversaturated, low quality, watermark, text",
        ip_adapter_weight=60,
        base_model="flux-dev-fp8",
    ),
]
```

- [ ] **Step 2: 写 `backend/tests/test_seeds/test_default_scenes.py`**

```python
from img2ec.seeds.default_scenes import DEFAULT_SCENES


def test_mvp_has_exactly_one_scene():
    assert len(DEFAULT_SCENES) == 1


def test_mvp_scene_has_required_fields():
    scene = DEFAULT_SCENES[0]
    assert scene.name == "大理石台·暖光"
    assert scene.category == "美妆/食品"
    assert "marble" in scene.prompt.lower()
    assert scene.base_model == "flux-dev-fp8"
    assert 0 <= scene.ip_adapter_weight <= 100
```

- [ ] **Step 3: 跑测试**

```bash
cd backend
pytest tests/test_seeds -v
```

Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(seeds): add MVP default scene 大理石台·暖光"
```

---

## Task 4: fs_layout 与 Finder 集成

**Files:**
- Create: `backend/img2ec/infra/fs_layout.py`
- Create: `backend/img2ec/infra/reveal.py`
- Create: `backend/tests/test_infra/test_fs_layout.py`
- Create: `backend/tests/test_infra/test_reveal.py`

- [ ] **Step 1: 写测试 `backend/tests/test_infra/test_fs_layout.py`**

```python
from pathlib import Path
import pytest

from img2ec.infra.fs_layout import slug, project_dir, sku_dir, source_dir, master_dir, outputs_dir, platform_dir


def test_slug_keeps_chinese():
    assert slug("蓝色保温杯 500ml") == "蓝色保温杯-500ml"


def test_slug_strips_special_chars():
    assert slug("a/b\\c?d:e*f") == "a-b-c-d-e-f"


def test_project_dir(tmp_path):
    root = tmp_path
    p = project_dir(root, "双11促销")
    assert p == root / "双11促销"


def test_sku_dir(tmp_path):
    p = sku_dir(tmp_path, "default", "蓝色保温杯")
    assert p == tmp_path / "default" / "蓝色保温杯"


def test_subdirs(tmp_path):
    skud = sku_dir(tmp_path, "default", "blue-cup")
    assert source_dir(skud) == skud / "source"
    assert master_dir(skud) == skud / "master"
    assert outputs_dir(skud) == skud / "outputs"
    assert platform_dir(skud, "douyin") == skud / "outputs" / "douyin"


def test_invalid_platform_rejected(tmp_path):
    skud = sku_dir(tmp_path, "p", "s")
    with pytest.raises(ValueError, match="invalid platform"):
        platform_dir(skud, "facebook")
```

- [ ] **Step 2: 跑测试看失败**

```bash
cd backend
pytest tests/test_infra/test_fs_layout.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'img2ec.infra.fs_layout'"

- [ ] **Step 3: 写 `backend/img2ec/infra/fs_layout.py`**

```python
import re
from pathlib import Path

VALID_PLATFORMS = {"douyin", "shipinhao", "taobao", "xiaohongshu"}
SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9一-龥_-]+")


def slug(s: str) -> str:
    """支持中文 + 英文 + 数字 + - _，其它字符替换成 -。"""
    out = SLUG_PATTERN.sub("-", s.strip())
    return out.strip("-")


def project_dir(root: Path, project_name: str) -> Path:
    return root / slug(project_name)


def sku_dir(root: Path, project_name: str, sku_name: str) -> Path:
    return project_dir(root, project_name) / slug(sku_name)


def source_dir(sku_d: Path) -> Path:
    return sku_d / "source"


def cutout_dir(sku_d: Path) -> Path:
    return sku_d / "cutout"


def master_dir(sku_d: Path) -> Path:
    return sku_d / "master"


def outputs_dir(sku_d: Path) -> Path:
    return sku_d / "outputs"


def platform_dir(sku_d: Path, platform: str) -> Path:
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"invalid platform: {platform}, must be one of {VALID_PLATFORMS}")
    return outputs_dir(sku_d) / platform


def ensure_sku_dirs(sku_d: Path) -> None:
    """创建 SKU 下所有子目录。"""
    for sub in (source_dir, cutout_dir, master_dir, outputs_dir):
        sub(sku_d).mkdir(parents=True, exist_ok=True)
    for p in VALID_PLATFORMS:
        platform_dir(sku_d, p).mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_infra/test_fs_layout.py -v
```

Expected: 5 passed

- [ ] **Step 5: 写测试 `backend/tests/test_infra/test_reveal.py`**

```python
import sys
from unittest.mock import patch

from img2ec.infra.reveal import reveal_in_finder


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_macos(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    reveal_in_finder("/tmp/foo")
    mock_run.assert_called_once_with(["open", "-R", "/tmp/foo"], check=False)


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_windows(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    reveal_in_finder("C:\\foo")
    mock_run.assert_called_once_with(["explorer.exe", "/select,", "C:\\foo"], check=False)


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_linux(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    reveal_in_finder("/tmp/foo")
    mock_run.assert_called_once_with(["xdg-open", "/tmp/foo"], check=False)
```

- [ ] **Step 6: 写 `backend/img2ec/infra/reveal.py`**

```python
import subprocess
import sys


def reveal_in_finder(path: str) -> None:
    """跨平台在文件管理器中显示该路径的父目录并选中。"""
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path], check=False)
    elif sys.platform == "win32":
        subprocess.run(["explorer.exe", "/select,", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)
```

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_infra -v
```

Expected: 8 passed

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(infra): add fs_layout (paths/slug) and reveal_in_finder"
```

---

## Task 5: bg_detect 模块

**Files:**
- Create: `backend/img2ec/core/bg_detect.py`
- Create: `backend/tests/fixtures/white_bg.jpg`（生成）
- Create: `backend/tests/fixtures/photo_bg.jpg`（生成）
- Create: `backend/tests/test_core/test_bg_detect.py`

- [ ] **Step 1: 用 Pillow 生成 fixture 图片**

写小脚本 `backend/tests/fixtures/_gen_fixtures.py` 一次性生成：
```python
"""运行一次生成测试用图片。"""
from pathlib import Path
import random
from PIL import Image, ImageDraw

HERE = Path(__file__).parent

# 1) 纯白底图：白色画布 + 中央灰色矩形（"商品"）
img = Image.new("RGB", (800, 800), (255, 255, 255))
ImageDraw.Draw(img).rectangle([200, 200, 600, 600], fill=(120, 120, 120))
img.save(HERE / "white_bg.jpg", quality=92)

# 2) 拍照背景：杂色噪点
img = Image.new("RGB", (800, 800), (180, 160, 140))
px = img.load()
random.seed(42)
for x in range(800):
    for y in range(800):
        r, g, b = px[x, y]
        n = random.randint(-40, 40)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
ImageDraw.Draw(img).rectangle([200, 200, 600, 600], fill=(80, 80, 80))
img.save(HERE / "photo_bg.jpg", quality=92)
```

跑：
```bash
cd backend
python tests/fixtures/_gen_fixtures.py
ls tests/fixtures/
```

Expected: 看到 `white_bg.jpg`、`photo_bg.jpg`

- [ ] **Step 2: 写测试 `backend/tests/test_core/test_bg_detect.py`**

```python
from img2ec.core.bg_detect import is_white_background


def test_white_bg_detected(fixtures_dir):
    assert is_white_background(fixtures_dir / "white_bg.jpg") is True


def test_photo_bg_not_detected(fixtures_dir):
    assert is_white_background(fixtures_dir / "photo_bg.jpg") is False
```

- [ ] **Step 3: 跑测试看失败**

```bash
pytest tests/test_core/test_bg_detect.py -v
```

Expected: FAIL ModuleNotFoundError

- [ ] **Step 4: 写 `backend/img2ec/core/bg_detect.py`**

```python
"""白底检测：抽样 4 边的边缘像素，判断方差与亮度。

判定规则：
  · 边缘像素均值 RGB 都 > 240（接近白）
  · 边缘像素方差 < 阈值（颜色一致）
"""
from pathlib import Path

from PIL import Image

EDGE_BRIGHTNESS_MIN = 240
EDGE_VARIANCE_MAX = 200.0
EDGE_BAND_PX = 20


def is_white_background(img_path: Path | str) -> bool:
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    band = EDGE_BAND_PX

    # 取四边的像素带
    top = img.crop((0, 0, w, band))
    bottom = img.crop((0, h - band, w, h))
    left = img.crop((0, 0, band, h))
    right = img.crop((w - band, 0, w, h))

    pixels: list[tuple[int, int, int]] = []
    for region in (top, bottom, left, right):
        pixels.extend(region.getdata())

    n = len(pixels)
    if n == 0:
        return False

    sum_r = sum(p[0] for p in pixels)
    sum_g = sum(p[1] for p in pixels)
    sum_b = sum(p[2] for p in pixels)
    mean_r, mean_g, mean_b = sum_r / n, sum_g / n, sum_b / n

    if mean_r < EDGE_BRIGHTNESS_MIN or mean_g < EDGE_BRIGHTNESS_MIN or mean_b < EDGE_BRIGHTNESS_MIN:
        return False

    var = sum((p[0] - mean_r) ** 2 + (p[1] - mean_g) ** 2 + (p[2] - mean_b) ** 2 for p in pixels) / n
    return var < EDGE_VARIANCE_MAX
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/test_core/test_bg_detect.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(core): add bg_detect with edge-sampling heuristic"
```

---

## Task 6: cutout 模块（rembg）

**Files:**
- Create: `backend/img2ec/core/cutout.py`
- Create: `backend/tests/test_core/test_cutout.py`

- [ ] **Step 1: 写测试 `backend/tests/test_core/test_cutout.py`**

```python
from PIL import Image

from img2ec.core.cutout import cutout_with_rembg


def test_cutout_returns_rgba_with_alpha(fixtures_dir, tmp_path):
    out_path = tmp_path / "front.png"
    cutout_with_rembg(fixtures_dir / "photo_bg.jpg", out_path)
    img = Image.open(out_path)
    assert img.mode == "RGBA"
    # 应该有透明像素（边缘被抠掉）
    alphas = {a for _, _, _, a in img.getdata() if hasattr(img, "mode")}
    # 简化：直接看角落像素是否透明
    corner_alpha = img.getpixel((0, 0))[3]
    assert corner_alpha == 0, f"expected transparent corner, got alpha={corner_alpha}"
```

- [ ] **Step 2: 跑测试看失败**

```bash
pytest tests/test_core/test_cutout.py -v
```

Expected: FAIL ModuleNotFoundError

- [ ] **Step 3: 写 `backend/img2ec/core/cutout.py`**

```python
"""rembg 抠图。模型首次调用时下载 (~150MB)，缓存在 ~/.u2net/。"""
from pathlib import Path

from PIL import Image
from rembg import remove


def cutout_with_rembg(src_path: Path | str, out_path: Path | str) -> None:
    """读取 src_path 的 RGB 图，rembg 去背景，保存为 RGBA PNG 到 out_path。"""
    src = Path(src_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as img:
        img_rgb = img.convert("RGB")

    cut = remove(img_rgb)  # 返回 PIL.Image RGBA
    cut.save(out, format="PNG")
```

- [ ] **Step 4: 跑测试（首次会下载模型，可能 30-60s）**

```bash
pytest tests/test_core/test_cutout.py -v -s
```

Expected: PASS（一次成功后模型缓存，后续秒级）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add rembg-based cutout"
```

---

## Task 7: ComfyUI client + workflow JSON

**Files:**
- Create: `backend/workflows/generate_master_1x1.json`
- Create: `backend/img2ec/infra/comfy_client.py`
- Create: `backend/tests/test_infra/test_comfy_client.py`

- [ ] **Step 1: 准备 ComfyUI workflow JSON**

`backend/workflows/generate_master_1x1.json`：先放最小骨架，工程师在 gpu box 的 ComfyUI 里搭好 1:1 master 生成 workflow（含 IPAdapter + ControlNet Canny + Flux dev FP8 KSampler），导出 API 格式 JSON 替换。骨架占位：

```json
{
  "_doc": "Phase 1 MVP: 1:1 master 生成 workflow API JSON。在 ComfyUI 上搭好后，菜单 Save (API Format) 导出替换此文件。需要的节点：LoadImage(cutout) → IPAdapterApply → KSampler → SaveImage。",
  "_inputs_doc": {
    "cutout_image": "节点 ID 用 LoadImage，文件名占位 __CUTOUT__",
    "prompt": "CLIPTextEncode positive，文本占位 __PROMPT__",
    "negative": "CLIPTextEncode negative，文本占位 __NEG__",
    "ip_weight": "IPAdapterApply.weight，占位 __IP_WEIGHT__",
    "seed": "KSampler.seed，占位 __SEED__"
  }
}
```

> 实施时由工程师在 gpu box 的 ComfyUI 用 manager 装 IPAdapter、ControlNet、Flux 节点，搭好 workflow 后导出 API JSON 覆盖此文件。文件路径不变。

- [ ] **Step 2: 写测试 `backend/tests/test_infra/test_comfy_client.py`**

```python
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from img2ec.infra.comfy_client import ComfyClient, ComfyError


@pytest.fixture
def workflow_path(tmp_path):
    p = tmp_path / "wf.json"
    p.write_text(json.dumps({
        "1": {"class_type": "LoadImage", "inputs": {"image": "__CUTOUT__"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "__PROMPT__"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "__NEG__"}},
        "4": {"class_type": "IPAdapterApply", "inputs": {"weight": "__IP_WEIGHT__"}},
        "5": {"class_type": "KSampler", "inputs": {"seed": "__SEED__"}},
    }))
    return p


def test_substitute_placeholders(workflow_path):
    c = ComfyClient("http://gpu:8188")
    rendered = c.render_workflow(
        workflow_path,
        cutout="front.png",
        prompt="on marble",
        neg="cluttered",
        ip_weight=60,
        seed=42,
    )
    nodes = rendered
    assert nodes["1"]["inputs"]["image"] == "front.png"
    assert nodes["2"]["inputs"]["text"] == "on marble"
    assert nodes["3"]["inputs"]["text"] == "cluttered"
    assert nodes["4"]["inputs"]["weight"] == 60
    assert nodes["5"]["inputs"]["seed"] == 42


@patch("img2ec.infra.comfy_client.httpx.Client.post")
def test_submit_prompt_returns_id(mock_post):
    mock_post.return_value.json.return_value = {"prompt_id": "abc123"}
    mock_post.return_value.raise_for_status = lambda: None
    c = ComfyClient("http://gpu:8188")
    pid = c.submit_prompt({"1": {"class_type": "X", "inputs": {}}})
    assert pid == "abc123"


@patch("img2ec.infra.comfy_client.httpx.Client.post")
def test_submit_prompt_raises_on_http_error(mock_post):
    mock_post.side_effect = Exception("connection refused")
    c = ComfyClient("http://gpu:8188")
    with pytest.raises(ComfyError):
        c.submit_prompt({})
```

- [ ] **Step 3: 写 `backend/img2ec/infra/comfy_client.py`**

```python
"""ComfyUI HTTP client。

工作流程：
1. POST /upload/image 上传 cutout
2. POST /prompt 提交 workflow（含占位符替换）
3. 轮询 GET /history/{prompt_id} 直到完成
4. GET /view 拉结果图
"""
import json
import time
from pathlib import Path
from typing import Any

import httpx


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def render_workflow(self, workflow_path: Path, **placeholders: Any) -> dict[str, Any]:
        """读 workflow JSON 模板，替换 __KEY__ 占位符为传入值。"""
        raw = workflow_path.read_text(encoding="utf-8")
        for k, v in placeholders.items():
            token = f"__{k.upper()}__"
            if isinstance(v, str):
                raw = raw.replace(f'"{token}"', json.dumps(v))
            else:
                raw = raw.replace(f'"{token}"', json.dumps(v))
        nodes = json.loads(raw)
        # 去掉文档键
        return {k: v for k, v in nodes.items() if not k.startswith("_")}

    def upload_image(self, image_path: Path) -> str:
        """上传图片到 ComfyUI 的 input/ 目录，返回它在那里的文件名。"""
        with open(image_path, "rb") as f:
            files = {"image": (image_path.name, f, "image/png")}
            try:
                resp = self._client.post(f"{self.base_url}/upload/image", files=files)
                resp.raise_for_status()
            except Exception as e:
                raise ComfyError(f"upload failed: {e}") from e
        return resp.json()["name"]

    def submit_prompt(self, workflow: dict[str, Any]) -> str:
        try:
            resp = self._client.post(f"{self.base_url}/prompt", json={"prompt": workflow})
            resp.raise_for_status()
        except Exception as e:
            raise ComfyError(f"submit failed: {e}") from e
        return resp.json()["prompt_id"]

    def wait_for_result(self, prompt_id: str, poll_interval: float = 1.0) -> dict[str, Any]:
        """轮询直到 prompt 完成，返回 history entry。"""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            resp = self._client.get(f"{self.base_url}/history/{prompt_id}")
            resp.raise_for_status()
            data = resp.json()
            if prompt_id in data:
                return data[prompt_id]
            time.sleep(poll_interval)
        raise ComfyError(f"timeout waiting for prompt {prompt_id}")

    def download_output(self, filename: str, subfolder: str, type_: str, dst_path: Path) -> None:
        params = {"filename": filename, "subfolder": subfolder, "type": type_}
        try:
            resp = self._client.get(f"{self.base_url}/view", params=params)
            resp.raise_for_status()
        except Exception as e:
            raise ComfyError(f"download failed: {e}") from e
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(resp.content)

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_infra/test_comfy_client.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(infra): add ComfyUI HTTP client and workflow placeholder template"
```

---

## Task 8: master_gen 模块

**Files:**
- Create: `backend/img2ec/core/master_gen.py`
- Create: `backend/tests/test_core/test_master_gen.py`

- [ ] **Step 1: 写测试 `backend/tests/test_core/test_master_gen.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock

from img2ec.core.master_gen import generate_master_1x1


def test_generate_master_calls_comfy_correctly(tmp_path):
    cutout = tmp_path / "front.png"
    cutout.write_bytes(b"fake png")
    out = tmp_path / "front-1x1.jpg"

    mock_client = MagicMock()
    mock_client.upload_image.return_value = "front.png"
    mock_client.render_workflow.return_value = {"5": {"class_type": "KSampler"}}
    mock_client.submit_prompt.return_value = "pid-123"
    mock_client.wait_for_result.return_value = {
        "outputs": {
            "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
        }
    }

    def fake_download(filename, subfolder, type_, dst):
        Path(dst).write_bytes(b"fake jpg")

    mock_client.download_output.side_effect = fake_download

    workflow_path = Path(__file__).parents[2] / "workflows" / "generate_master_1x1.json"
    generate_master_1x1(
        client=mock_client,
        workflow_path=workflow_path,
        cutout_path=cutout,
        prompt="on marble",
        negative_prompt="cluttered",
        ip_weight=60,
        seed=42,
        output_path=out,
    )

    assert out.exists()
    mock_client.upload_image.assert_called_once_with(cutout)
    mock_client.submit_prompt.assert_called_once()
    mock_client.wait_for_result.assert_called_once_with("pid-123")
```

- [ ] **Step 2: 跑测试看失败**

```bash
pytest tests/test_core/test_master_gen.py -v
```

Expected: FAIL ModuleNotFoundError

- [ ] **Step 3: 写 `backend/img2ec/core/master_gen.py`**

```python
"""调用 ComfyUI 生成 1 张 master（Phase 1 MVP：仅 1:1）。

Phase 2 扩展为 generate_masters_all() 同时生 5 张 (1:1, long, 3:4, 9:16, 16:9)。
"""
from pathlib import Path

from img2ec.infra.comfy_client import ComfyClient, ComfyError


def generate_master_1x1(
    *,
    client: ComfyClient,
    workflow_path: Path,
    cutout_path: Path,
    prompt: str,
    negative_prompt: str,
    ip_weight: int,
    seed: int,
    output_path: Path,
) -> Path:
    """跑 ComfyUI 生 1 张 1:1 master，存到 output_path。"""
    uploaded_name = client.upload_image(cutout_path)
    workflow = client.render_workflow(
        workflow_path,
        cutout=uploaded_name,
        prompt=prompt,
        neg=negative_prompt,
        ip_weight=ip_weight,
        seed=seed,
    )
    prompt_id = client.submit_prompt(workflow)
    history = client.wait_for_result(prompt_id)

    images = _collect_output_images(history)
    if not images:
        raise ComfyError(f"no output images for prompt {prompt_id}")
    img = images[0]
    client.download_output(
        filename=img["filename"],
        subfolder=img.get("subfolder", ""),
        type_=img.get("type", "output"),
        dst_path=output_path,
    )
    return output_path


def _collect_output_images(history: dict) -> list[dict]:
    out: list[dict] = []
    for node_outputs in history.get("outputs", {}).values():
        out.extend(node_outputs.get("images", []))
    return out
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_core/test_master_gen.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add master_gen for 1:1 ComfyUI generation"
```

---

## Task 9: derive 模块（Pillow 派生 4 平台 1:1 主图）

**Files:**
- Create: `backend/img2ec/core/derive.py`
- Create: `backend/tests/test_core/test_derive.py`

- [ ] **Step 1: 写测试 `backend/tests/test_core/test_derive.py`**

```python
from PIL import Image

from img2ec.core.derive import PLATFORMS_1X1_SIZES, derive_main_1x1_for_platforms


def test_platforms_have_expected_sizes():
    assert PLATFORMS_1X1_SIZES == {
        "douyin": (1080, 1080),
        "shipinhao": (800, 800),
        "taobao": (800, 800),
        "xiaohongshu": (1080, 1080),
    }


def test_derive_creates_per_platform_files(tmp_path):
    # 准备一张 1:1 master
    master = Image.new("RGB", (1500, 1500), (200, 100, 50))
    master_path = tmp_path / "master-1x1.jpg"
    master.save(master_path, quality=92)

    out_dir = tmp_path / "outputs"
    paths = derive_main_1x1_for_platforms(master_path, out_dir, image_stem="front")

    assert set(paths.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    for platform, p in paths.items():
        assert p.exists()
        with Image.open(p) as img:
            assert img.size == PLATFORMS_1X1_SIZES[platform]


def test_derive_handles_non_square_master_by_center_crop(tmp_path):
    # 非 1:1 输入：测试中央裁切
    master = Image.new("RGB", (2000, 1500), (50, 50, 50))
    master_path = tmp_path / "master.jpg"
    master.save(master_path, quality=92)

    out_dir = tmp_path / "outputs"
    paths = derive_main_1x1_for_platforms(master_path, out_dir, image_stem="x")
    with Image.open(paths["douyin"]) as img:
        assert img.size == (1080, 1080)
```

- [ ] **Step 2: 跑测试看失败**

```bash
pytest tests/test_core/test_derive.py -v
```

Expected: FAIL ModuleNotFoundError

- [ ] **Step 3: 写 `backend/img2ec/core/derive.py`**

```python
"""从 master 派生平台尺寸。

Phase 1 MVP：只派生 4 平台的 1:1 主图。
Phase 2 扩展为完整 5 master + 15 派生。
"""
from pathlib import Path

from PIL import Image

from img2ec.infra.fs_layout import platform_dir, outputs_dir, VALID_PLATFORMS

PLATFORMS_1X1_SIZES: dict[str, tuple[int, int]] = {
    "douyin": (1080, 1080),
    "shipinhao": (800, 800),
    "taobao": (800, 800),
    "xiaohongshu": (1080, 1080),
}


def _center_crop_to_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def derive_main_1x1_for_platforms(
    master_path: Path,
    sku_outputs_root: Path,
    image_stem: str,
) -> dict[str, Path]:
    """对每平台输出主图。返回 {platform: dst_path} 映射。"""
    sku_outputs_root.mkdir(parents=True, exist_ok=True)
    with Image.open(master_path) as src:
        src_rgb = src.convert("RGB")
        square = _center_crop_to_square(src_rgb) if src_rgb.size[0] != src_rgb.size[1] else src_rgb

        out_paths: dict[str, Path] = {}
        for platform, size in PLATFORMS_1X1_SIZES.items():
            target_dir = sku_outputs_root / platform
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / f"{image_stem}-main-{size[0]}x{size[1]}.jpg"
            resized = square.resize(size, Image.LANCZOS)
            resized.save(dst, quality=90)
            out_paths[platform] = dst

    return out_paths
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_core/test_derive.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): add Pillow-based derive for 4 platforms 1:1 main images"
```

---

## Task 10: pipeline 编排 + Celery 任务

**Files:**
- Create: `backend/img2ec/celery_app.py`
- Create: `backend/img2ec/core/pipeline.py`
- Create: `backend/img2ec/tasks/__init__.py`
- Create: `backend/img2ec/tasks/pipeline_tasks.py`
- Create: `backend/tests/test_core/test_pipeline.py`

- [ ] **Step 1: 写 `backend/img2ec/celery_app.py`**

```python
from celery import Celery

from img2ec.config import get_settings

settings = get_settings()

celery_app = Celery(
    "img2ec",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["img2ec.tasks.pipeline_tasks"],
)

celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
```

- [ ] **Step 2: 写测试 `backend/tests/test_core/test_pipeline.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from img2ec.core.pipeline import process_one_image


@pytest.fixture
def setup_dirs(tmp_path):
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src = src_dir / "front.jpg"
    src.write_bytes(b"fake jpg")
    return tmp_path, src


@patch("img2ec.core.pipeline.derive_main_1x1_for_platforms")
@patch("img2ec.core.pipeline.generate_master_1x1")
@patch("img2ec.core.pipeline.cutout_with_rembg")
@patch("img2ec.core.pipeline.is_white_background")
def test_pipeline_white_bg_skips_cutout(
    mock_bg, mock_cut, mock_master, mock_derive, setup_dirs
):
    sku_dir, src = setup_dirs
    mock_bg.return_value = True
    mock_derive.return_value = {"douyin": sku_dir / "out.jpg"}

    progress: list[tuple[str, int]] = []
    process_one_image(
        src_path=src,
        sku_dir=sku_dir,
        image_stem="front",
        scene_prompt="p",
        scene_neg="n",
        ip_weight=60,
        seed=1,
        comfy_client=MagicMock(),
        workflow_path=Path("wf.json"),
        on_progress=lambda stage, pct: progress.append((stage, pct)),
    )

    mock_cut.assert_not_called()
    mock_master.assert_called_once()
    mock_derive.assert_called_once()
    stages = [s for s, _ in progress]
    assert "cutting" not in stages
    assert "generating" in stages
    assert "composing" in stages


@patch("img2ec.core.pipeline.derive_main_1x1_for_platforms")
@patch("img2ec.core.pipeline.generate_master_1x1")
@patch("img2ec.core.pipeline.cutout_with_rembg")
@patch("img2ec.core.pipeline.is_white_background")
def test_pipeline_photo_bg_runs_cutout(
    mock_bg, mock_cut, mock_master, mock_derive, setup_dirs
):
    sku_dir, src = setup_dirs
    mock_bg.return_value = False
    mock_derive.return_value = {"douyin": sku_dir / "out.jpg"}

    process_one_image(
        src_path=src,
        sku_dir=sku_dir,
        image_stem="front",
        scene_prompt="p",
        scene_neg="n",
        ip_weight=60,
        seed=1,
        comfy_client=MagicMock(),
        workflow_path=Path("wf.json"),
    )

    mock_cut.assert_called_once()
    mock_master.assert_called_once()
```

- [ ] **Step 3: 写 `backend/img2ec/core/pipeline.py`**

```python
"""单张原图的处理流水线（同步函数；Celery task 包它）。

Phase 1 MVP：bg_detect → (cutout if needed) → master_gen 1:1 → derive 4 平台
"""
from pathlib import Path
from typing import Callable

from img2ec.core.bg_detect import is_white_background
from img2ec.core.cutout import cutout_with_rembg
from img2ec.core.derive import derive_main_1x1_for_platforms
from img2ec.core.master_gen import generate_master_1x1
from img2ec.infra.comfy_client import ComfyClient
from img2ec.infra.fs_layout import cutout_dir, master_dir, outputs_dir

ProgressCb = Callable[[str, int], None]


def process_one_image(
    *,
    src_path: Path,
    sku_dir: Path,
    image_stem: str,
    scene_prompt: str,
    scene_neg: str,
    ip_weight: int,
    seed: int,
    comfy_client: ComfyClient,
    workflow_path: Path,
    on_progress: ProgressCb | None = None,
) -> dict[str, Path]:
    """跑完返回派生输出 {platform: path} 字典。"""
    cb: ProgressCb = on_progress or (lambda _s, _p: None)

    # 阶段 1: 抠图
    cb("cutting", 0)
    if is_white_background(src_path):
        cutout_path = src_path  # 白底直接拿原图当 cutout
    else:
        cutout_path = cutout_dir(sku_dir) / f"{image_stem}.png"
        cutout_with_rembg(src_path, cutout_path)
    cb("cutting", 100)

    # 阶段 2: 生 master
    cb("generating", 0)
    master_path = master_dir(sku_dir) / f"{image_stem}-1x1.jpg"
    generate_master_1x1(
        client=comfy_client,
        workflow_path=workflow_path,
        cutout_path=cutout_path,
        prompt=scene_prompt,
        negative_prompt=scene_neg,
        ip_weight=ip_weight,
        seed=seed,
        output_path=master_path,
    )
    cb("generating", 100)

    # 阶段 3: 派生
    cb("composing", 0)
    derived = derive_main_1x1_for_platforms(
        master_path=master_path,
        sku_outputs_root=outputs_dir(sku_dir),
        image_stem=image_stem,
    )
    cb("composing", 100)

    return derived
```

- [ ] **Step 4: 跑 pipeline 测试**

```bash
pytest tests/test_core/test_pipeline.py -v
```

Expected: 2 passed

- [ ] **Step 5: 写 `backend/img2ec/tasks/pipeline_tasks.py`**

```python
"""Celery 任务：处理单张原图，同步 DB 状态。"""
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.config import get_settings
from img2ec.core.pipeline import process_one_image
from img2ec.db import SessionLocal
from img2ec.infra.comfy_client import ComfyClient, ComfyError
from img2ec.infra.fs_layout import sku_dir as sku_dir_fn, ensure_sku_dirs
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Scene


WORKFLOW_PATH = Path(__file__).parents[2] / "workflows" / "generate_master_1x1.json"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_image_task(self, image_id: str) -> str:
    settings = get_settings()
    db = SessionLocal()
    try:
        img: SourceImage | None = db.get(SourceImage, image_id)
        if img is None:
            return "missing"

        sku: SKU = db.get(SKU, img.sku_id)
        project: Project = db.get(Project, sku.project_id)
        scene: Scene | None = db.get(Scene, sku.scene_id) if sku.scene_id else None
        if scene is None:
            img.status = ImageStatus.FAILED.value
            img.err_msg = "no scene assigned to SKU"
            db.commit()
            return "no_scene"

        skud = sku_dir_fn(Path(project.root_path).parent, project.name, sku.name)
        ensure_sku_dirs(skud)

        client = ComfyClient(settings.comfy_url, timeout=settings.comfy_timeout)

        def update_progress(stage: str, pct: int) -> None:
            img.status = stage if stage in ("cutting", "generating", "composing") else img.status
            img.progress = pct
            db.commit()

        try:
            derived = process_one_image(
                src_path=Path(img.src_path),
                sku_dir=skud,
                image_stem=Path(img.name).stem,
                scene_prompt=scene.prompt,
                scene_neg=scene.negative_prompt,
                ip_weight=scene.ip_adapter_weight,
                seed=42,
                comfy_client=client,
                workflow_path=WORKFLOW_PATH,
                on_progress=update_progress,
            )
            img.derived_paths = {k: str(v) for k, v in derived.items()}
            img.master_paths = {"1:1": str(skud / "master" / f"{Path(img.name).stem}-1x1.jpg")}
            img.status = ImageStatus.DONE.value
            img.progress = 100
            db.commit()
        except ComfyError as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = str(e)
            db.commit()
            raise self.retry(exc=e)
        except Exception as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = f"{type(e).__name__}: {e}"
            db.commit()
            raise
        finally:
            client.close()

        # 聚合 SKU 状态
        sku.status = _aggregate_sku_status(sku, db)
        db.commit()
        return "done"
    finally:
        db.close()


def _aggregate_sku_status(sku: SKU, db) -> str:
    images = db.query(SourceImage).filter_by(sku_id=sku.id).all()
    statuses = {i.status for i in images}
    if statuses & {ImageStatus.PENDING.value, ImageStatus.CUTTING.value,
                   ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value}:
        return SKUStatus.RUNNING.value
    if ImageStatus.FAILED.value in statuses:
        return SKUStatus.ERROR.value
    if statuses == {ImageStatus.DONE.value}:
        return SKUStatus.DONE.value
    return SKUStatus.READY.value
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(pipeline): add core pipeline orchestration and Celery task wrapper"
```

---

## Task 11: API: Projects + Scenes（含默认场景导入）

**Files:**
- Create: `backend/img2ec/schemas/project.py`
- Create: `backend/img2ec/schemas/scene.py`
- Create: `backend/img2ec/api/__init__.py`
- Create: `backend/img2ec/api/projects.py`
- Create: `backend/img2ec/api/scenes.py`
- Modify: `backend/img2ec/main.py` 注册路由
- Create: `backend/tests/test_api/test_projects.py`
- Create: `backend/tests/test_api/test_scenes.py`

- [ ] **Step 1: 写 schemas `backend/img2ec/schemas/project.py`**

```python
from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    desc: str = ""
    copy_default_scenes: bool = True


class ProjectOut(BaseModel):
    id: str
    name: str
    desc: str
    root_path: str
    sku_count: int
    scene_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: 写 schemas `backend/img2ec/schemas/scene.py`**

```python
from datetime import datetime
from pydantic import BaseModel, Field


class SceneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = "自定义"
    desc: str = ""
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = ""
    ip_adapter_weight: int = Field(60, ge=0, le=100)
    base_model: str = "flux-dev-fp8"


class SceneOut(BaseModel):
    id: str
    project_id: str
    name: str
    category: str
    desc: str
    prompt: str
    negative_prompt: str
    ip_adapter_weight: int
    base_model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: 写 `backend/img2ec/api/projects.py`**

```python
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import project_dir
from img2ec.models import Project, Scene, SKU
from img2ec.schemas.project import ProjectCreate, ProjectOut
from img2ec.seeds.default_scenes import DEFAULT_SCENES

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_session)) -> list[ProjectOut]:
    rows = db.query(Project).all()
    return [_to_out(p, db) for p in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_session)) -> ProjectOut:
    if db.query(Project).filter_by(name=payload.name).first():
        raise HTTPException(409, f"project '{payload.name}' already exists")

    settings = get_settings()
    pid = str(uuid.uuid4())
    pdir = project_dir(settings.root_path, payload.name)
    pdir.mkdir(parents=True, exist_ok=True)

    p = Project(id=pid, name=payload.name, desc=payload.desc, root_path=str(pdir))
    db.add(p)

    if payload.copy_default_scenes:
        for seed in DEFAULT_SCENES:
            db.add(Scene(
                id=str(uuid.uuid4()),
                project_id=pid,
                name=seed.name,
                category=seed.category,
                desc=seed.desc,
                prompt=seed.prompt,
                negative_prompt=seed.negative_prompt,
                ip_adapter_weight=seed.ip_adapter_weight,
                base_model=seed.base_model,
            ))

    db.commit()
    db.refresh(p)
    return _to_out(p, db)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_session)) -> ProjectOut:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    return _to_out(p, db)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_session)) -> None:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    db.delete(p)
    db.commit()


def _to_out(p: Project, db: Session) -> ProjectOut:
    sku_count = db.query(SKU).filter_by(project_id=p.id).count()
    scene_count = db.query(Scene).filter_by(project_id=p.id).count()
    return ProjectOut.model_validate({
        "id": p.id, "name": p.name, "desc": p.desc, "root_path": p.root_path,
        "sku_count": sku_count, "scene_count": scene_count,
        "created_at": p.created_at, "updated_at": p.updated_at,
    })
```

- [ ] **Step 4: 写 `backend/img2ec/api/scenes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import Project, Scene
from img2ec.schemas.scene import SceneCreate, SceneOut

router = APIRouter(prefix="/api/projects/{project_id}/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneOut])
def list_scenes(project_id: str, db: Session = Depends(get_session)) -> list[Scene]:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    return db.query(Scene).filter_by(project_id=project_id).all()


@router.post("", response_model=SceneOut, status_code=201)
def create_scene(project_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> Scene:
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    sc = Scene(id=str(uuid.uuid4()), project_id=project_id, **payload.model_dump())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.put("/{scene_id}", response_model=SceneOut)
def update_scene(project_id: str, scene_id: str, payload: SceneCreate, db: Session = Depends(get_session)) -> Scene:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    for k, v in payload.model_dump().items():
        setattr(sc, k, v)
    db.commit()
    db.refresh(sc)
    return sc


@router.delete("/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_session)) -> None:
    sc = db.get(Scene, scene_id)
    if sc is None or sc.project_id != project_id:
        raise HTTPException(404, "scene not found")
    db.delete(sc)
    db.commit()
```

- [ ] **Step 5: 注册路由 `backend/img2ec/main.py`**

修改 `create_app()` 函数，在 `app.add_middleware(...)` 之后加：
```python
    from img2ec.api import projects, scenes
    app.include_router(projects.router)
    app.include_router(scenes.router)
```

- [ ] **Step 6: 写共享测试 fixtures `backend/tests/test_api/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from img2ec.db import get_session
from img2ec.main import create_app
from img2ec.models import Base


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IMG2EC_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("IMG2EC_ROOT_PATH", str(tmp_path / "projects"))

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    app = create_app()

    def override_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_session
    return app


@pytest.fixture
def cli(app_with_db):
    return TestClient(app_with_db)
```

- [ ] **Step 7: 写测试 `backend/tests/test_api/test_projects.py`**

```python
def test_create_project_with_default_scenes(cli):
    r = cli.post("/api/projects", json={"name": "default", "desc": "d", "copy_default_scenes": True})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "default"
    assert data["scene_count"] == 1


def test_create_project_without_scenes(cli):
    r = cli.post("/api/projects", json={"name": "empty", "copy_default_scenes": False})
    assert r.status_code == 201
    assert r.json()["scene_count"] == 0


def test_duplicate_project_returns_409(cli):
    cli.post("/api/projects", json={"name": "dup", "copy_default_scenes": False})
    r = cli.post("/api/projects", json={"name": "dup", "copy_default_scenes": False})
    assert r.status_code == 409


def test_list_and_delete(cli):
    cli.post("/api/projects", json={"name": "a", "copy_default_scenes": False})
    cli.post("/api/projects", json={"name": "b", "copy_default_scenes": False})
    assert len(cli.get("/api/projects").json()) == 2
    pid_a = cli.get("/api/projects").json()[0]["id"]
    assert cli.delete(f"/api/projects/{pid_a}").status_code == 204
    assert len(cli.get("/api/projects").json()) == 1
```

- [ ] **Step 8: 写测试 `backend/tests/test_api/test_scenes.py`**

```python
def test_scene_crud(cli):
    pid = cli.post("/api/projects", json={"name": "p", "copy_default_scenes": True}).json()["id"]

    # list 应该有 1 个内置场景
    scenes = cli.get(f"/api/projects/{pid}/scenes").json()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "大理石台·暖光"

    # create
    r = cli.post(f"/api/projects/{pid}/scenes", json={
        "name": "测试场景", "category": "测试", "prompt": "test prompt"
    })
    assert r.status_code == 201
    sid = r.json()["id"]

    # update
    r = cli.put(f"/api/projects/{pid}/scenes/{sid}", json={
        "name": "改名后", "category": "测试", "prompt": "new prompt"
    })
    assert r.status_code == 200
    assert r.json()["name"] == "改名后"

    # delete
    assert cli.delete(f"/api/projects/{pid}/scenes/{sid}").status_code == 204
```

- [ ] **Step 9: 跑测试**

```bash
pytest tests/test_api -v
```

Expected: 6 passed

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(api): add Projects and Scenes CRUD with default scene seeding"
```

---

## Task 12: API: SKUs + 图片上传 + process

**Files:**
- Create: `backend/img2ec/schemas/sku.py`
- Create: `backend/img2ec/api/skus.py`
- Create: `backend/img2ec/api/outputs.py`
- Create: `backend/img2ec/api/fs.py`
- Modify: `backend/img2ec/main.py` 注册新路由
- Create: `backend/tests/test_api/test_skus.py`

- [ ] **Step 1: 写 schemas `backend/img2ec/schemas/sku.py`**

```python
from datetime import datetime
from pydantic import BaseModel, Field


class SKUCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    scene_id: str | None = None


class SourceImageOut(BaseModel):
    id: str
    name: str
    src_path: str
    status: str
    progress: int
    err_msg: str | None
    master_paths: dict
    derived_paths: dict

    model_config = {"from_attributes": True}


class SKUOut(BaseModel):
    id: str
    project_id: str
    scene_id: str | None
    name: str
    status: str
    images: list[SourceImageOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: 写 `backend/img2ec/api/skus.py`**

```python
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir, ensure_sku_dirs, source_dir
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus
from img2ec.schemas.sku import SKUCreate, SKUOut

router = APIRouter(prefix="/api/projects/{project_id}/skus", tags=["skus"])


@router.get("", response_model=list[SKUOut])
def list_skus(project_id: str, db: Session = Depends(get_session)) -> list[SKU]:
    return db.query(SKU).filter_by(project_id=project_id).all()


@router.post("", response_model=SKUOut, status_code=201)
def create_sku(project_id: str, payload: SKUCreate, db: Session = Depends(get_session)) -> SKU:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    sku = SKU(id=str(uuid.uuid4()), project_id=project_id, name=payload.name,
              scene_id=payload.scene_id, status=SKUStatus.DRAFT.value)
    db.add(sku)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, payload.name)
    ensure_sku_dirs(skud)

    db.commit()
    db.refresh(sku)
    return sku


@router.get("/{sku_id}", response_model=SKUOut)
def get_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    return sku


@router.delete("/{sku_id}", status_code=204)
def delete_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> None:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    db.delete(sku)
    db.commit()


@router.post("/{sku_id}/images", response_model=SKUOut, status_code=201)
def upload_image(
    project_id: str, sku_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, project_id)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    src_d = source_dir(skud)
    src_d.mkdir(parents=True, exist_ok=True)
    dst = src_d / file.filename
    dst.write_bytes(file.file.read())

    img = SourceImage(
        id=str(uuid.uuid4()), sku_id=sku.id, name=file.filename, src_path=str(dst),
        status=ImageStatus.PENDING.value,
    )
    db.add(img)
    if sku.status == SKUStatus.DRAFT.value:
        sku.status = SKUStatus.READY.value
    db.commit()
    db.refresh(sku)
    return sku


@router.delete("/{sku_id}/images/{image_id}", status_code=204)
def delete_image(project_id: str, sku_id: str, image_id: str, db: Session = Depends(get_session)) -> None:
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if img.status not in (ImageStatus.PENDING.value, ImageStatus.FAILED.value):
        raise HTTPException(409, "cannot delete non-pending image")
    Path(img.src_path).unlink(missing_ok=True)
    db.delete(img)
    db.commit()


@router.post("/{sku_id}/process", status_code=202)
def process_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.scene_id is None:
        raise HTTPException(400, "no scene assigned")

    targets = [i for i in sku.images if i.status in (ImageStatus.PENDING.value, ImageStatus.FAILED.value)]
    if not targets:
        raise HTTPException(400, "no pending or failed images")

    sku.status = SKUStatus.RUNNING.value
    for img in targets:
        img.status = ImageStatus.PENDING.value
    db.commit()

    # 派发 Celery 任务
    from img2ec.tasks.pipeline_tasks import process_image_task
    for img in targets:
        process_image_task.delay(img.id)

    return {"queued": len(targets)}
```

- [ ] **Step 3: 写 `backend/img2ec/api/outputs.py`**

```python
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import outputs_dir, sku_dir
from img2ec.models import Project, SKU

router = APIRouter(prefix="/api", tags=["outputs"])


@router.get("/skus/{sku_id}/download")
def download_sku_zip(sku_id: str, db: Session = Depends(get_session)):
    sku = db.get(SKU, sku_id)
    if sku is None:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, sku.project_id)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    outd = outputs_dir(skud)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in outd.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(outd))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sku.name}.zip"'},
    )
```

- [ ] **Step 4: 写 `backend/img2ec/api/fs.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from img2ec.infra.reveal import reveal_in_finder

router = APIRouter(prefix="/api/fs", tags=["fs"])


class RevealReq(BaseModel):
    path: str


@router.post("/reveal", status_code=204)
def reveal(payload: RevealReq) -> None:
    if not payload.path:
        raise HTTPException(400, "path required")
    reveal_in_finder(payload.path)
```

- [ ] **Step 5: 注册新路由 `backend/img2ec/main.py`**

```python
    from img2ec.api import projects, scenes, skus, outputs, fs
    app.include_router(projects.router)
    app.include_router(scenes.router)
    app.include_router(skus.router)
    app.include_router(outputs.router)
    app.include_router(fs.router)
```

- [ ] **Step 6: 写测试 `backend/tests/test_api/test_skus.py`**

```python
import io


def _setup_project_with_scene(cli):
    pid = cli.post("/api/projects", json={"name": "p", "copy_default_scenes": True}).json()["id"]
    sid = cli.get(f"/api/projects/{pid}/scenes").json()[0]["id"]
    return pid, sid


def test_sku_create_with_scene(cli):
    pid, sid = _setup_project_with_scene(cli)
    r = cli.post(f"/api/projects/{pid}/skus", json={"name": "蓝色保温杯", "scene_id": sid})
    assert r.status_code == 201
    assert r.json()["name"] == "蓝色保温杯"
    assert r.json()["status"] == "draft"


def test_upload_image_changes_status_to_ready(cli):
    pid, sid = _setup_project_with_scene(cli)
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x", "scene_id": sid}).json()["id"]

    files = {"file": ("front.jpg", io.BytesIO(b"fake jpg"), "image/jpeg")}
    r = cli.post(f"/api/projects/{pid}/skus/{sku_id}/images", files=files)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    assert len(r.json()["images"]) == 1
    assert r.json()["images"][0]["name"] == "front.jpg"


def test_process_without_scene_returns_400(cli):
    pid = cli.post("/api/projects", json={"name": "p2", "copy_default_scenes": False}).json()["id"]
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x"}).json()["id"]
    r = cli.post(f"/api/projects/{pid}/skus/{sku_id}/process")
    assert r.status_code == 400


def test_delete_pending_image(cli):
    pid, sid = _setup_project_with_scene(cli)
    sku_id = cli.post(f"/api/projects/{pid}/skus", json={"name": "x", "scene_id": sid}).json()["id"]
    files = {"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")}
    sku = cli.post(f"/api/projects/{pid}/skus/{sku_id}/images", files=files).json()
    iid = sku["images"][0]["id"]
    r = cli.delete(f"/api/projects/{pid}/skus/{sku_id}/images/{iid}")
    assert r.status_code == 204
```

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_api/test_skus.py -v
```

Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(api): add SKUs CRUD, image upload, process trigger, zip download, fs reveal"
```

---

## Task 13: 前端：项目列表 + 顶栏 + 新建项目

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/types.ts`
- Create: `frontend/app/providers.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/projects/page.tsx`
- Create: `frontend/components/NewProjectModal.tsx`

- [ ] **Step 1: 写 `frontend/lib/types.ts`**

```ts
export interface Project {
  id: string;
  name: string;
  desc: string;
  root_path: string;
  sku_count: number;
  scene_count: number;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  name: string;
  category: string;
  desc: string;
  prompt: string;
  negative_prompt: string;
  ip_adapter_weight: number;
  base_model: string;
}

export type ImageStatus = "pending" | "cutting" | "generating" | "composing" | "done" | "failed";

export interface SourceImage {
  id: string;
  name: string;
  src_path: string;
  status: ImageStatus;
  progress: number;
  err_msg: string | null;
  master_paths: Record<string, string>;
  derived_paths: Record<string, string>;
}

export type SKUStatus = "draft" | "ready" | "running" | "done" | "error";

export interface SKU {
  id: string;
  project_id: string;
  scene_id: string | null;
  name: string;
  status: SKUStatus;
  images: SourceImage[];
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: 写 `frontend/lib/api.ts`**

```ts
const BASE = "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listProjects: () => req<import("./types").Project[]>("/api/projects"),
  createProject: (payload: { name: string; desc?: string; copy_default_scenes?: boolean }) =>
    req<import("./types").Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => req<void>(`/api/projects/${id}`, { method: "DELETE" }),

  listScenes: (pid: string) => req<import("./types").Scene[]>(`/api/projects/${pid}/scenes`),
  createScene: (pid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes`, { method: "POST", body: JSON.stringify(payload) }),
  updateScene: (pid: string, sid: string, payload: Partial<import("./types").Scene>) =>
    req<import("./types").Scene>(`/api/projects/${pid}/scenes/${sid}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteScene: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/scenes/${sid}`, { method: "DELETE" }),

  listSkus: (pid: string) => req<import("./types").SKU[]>(`/api/projects/${pid}/skus`),
  getSku: (pid: string, sid: string) => req<import("./types").SKU>(`/api/projects/${pid}/skus/${sid}`),
  createSku: (pid: string, payload: { name: string; scene_id?: string | null }) =>
    req<import("./types").SKU>(`/api/projects/${pid}/skus`, { method: "POST", body: JSON.stringify(payload) }),
  uploadImage: async (pid: string, sid: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/projects/${pid}/skus/${sid}/images`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<import("./types").SKU>;
  },
  deleteImage: (pid: string, sid: string, iid: string) =>
    req<void>(`/api/projects/${pid}/skus/${sid}/images/${iid}`, { method: "DELETE" }),
  processSku: (pid: string, sid: string) =>
    req<{ queued: number }>(`/api/projects/${pid}/skus/${sid}/process`, { method: "POST" }),
  deleteSku: (pid: string, sid: string) => req<void>(`/api/projects/${pid}/skus/${sid}`, { method: "DELETE" }),

  reveal: (path: string) => req<void>("/api/fs/reveal", { method: "POST", body: JSON.stringify({ path }) }),
  downloadSku: (sid: string) => `/api/skus/${sid}/download`,
};
```

- [ ] **Step 3: 写 `frontend/app/providers.tsx`**

```tsx
"use client";
import { SWRConfig } from "swr";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ revalidateOnFocus: false, dedupingInterval: 1000 }}>
      {children}
    </SWRConfig>
  );
}
```

- [ ] **Step 4: 修改 `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = { title: "img2ec" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: 写 `frontend/components/NewProjectModal.tsx`**

```tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function NewProjectModal({
  onClose, onCreated,
}: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [copyScenes, setCopyScenes] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name.trim()) return setErr("项目名必填");
    setBusy(true);
    try {
      await api.createProject({ name: name.trim(), desc: desc.trim(), copy_default_scenes: copyScenes });
      onCreated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[440px] max-w-[600px]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">新建项目</h2>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">项目名</label>
          <input value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm"
            placeholder="例如：双11促销" autoFocus />
        </div>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">说明（可选）</label>
          <textarea value={desc} onChange={e => setDesc(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" rows={2} />
        </div>
        <label className="flex items-center gap-2 text-sm mb-4">
          <input type="checkbox" checked={copyScenes} onChange={e => setCopyScenes(e.target.checked)} />
          复制默认场景（推荐：内置 1 个"大理石台·暖光"）
        </label>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>
            {busy ? "创建中…" : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 写 `frontend/app/projects/page.tsx`**

```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { NewProjectModal } from "@/components/NewProjectModal";

export default function ProjectsPage() {
  const { data, mutate, isLoading } = useSWR("projects", () => api.listProjects());
  const [showModal, setShowModal] = useState(false);

  return (
    <main className="max-w-6xl mx-auto p-4">
      <header className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3">
        <h1 className="text-lg font-bold">img2ec</h1>
        <span className="text-xs opacity-60">所有项目</span>
        <div className="flex-1" />
        <button onClick={() => setShowModal(true)}
          className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 新建项目</button>
      </header>

      {isLoading && <p className="opacity-60">加载中…</p>}
      {data && data.length === 0 && (
        <div className="text-center py-12 opacity-60">还没有项目，点右上"新建项目"开始</div>
      )}
      <div className="grid grid-cols-3 gap-3">
        {data?.map(p => (
          <Link key={p.id} href={`/projects/${p.id}/skus`}
            className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-4 transition">
            <div className="h-20 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded mb-3 flex items-center justify-center text-3xl opacity-50">📁</div>
            <h3 className="text-sm font-semibold mb-1">{p.name}</h3>
            <p className="text-xs opacity-60">{p.desc || "（无说明）"}</p>
            <p className="text-xs opacity-60 mt-1">{p.sku_count} SKU · {p.scene_count} 场景</p>
          </Link>
        ))}
      </div>

      {showModal && <NewProjectModal onClose={() => setShowModal(false)}
        onCreated={() => { setShowModal(false); mutate(); }} />}
    </main>
  );
}
```

- [ ] **Step 7: 启动后端 + 前端，手测**

```bash
# 终端 1
cd backend && source .venv/bin/activate && uvicorn img2ec.main:app --reload --port 8000

# 终端 2
cd frontend && npm run dev

# 浏览器：http://localhost:3000
```

Expected: 看到空项目页 → 点"新建项目"→ 填名字 → 创建 → 列表里出现卡片

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(frontend): add Projects page with NewProjectModal"
```

---

## Task 14: 前端：场景库 + 项目内布局

**Files:**
- Create: `frontend/app/projects/[pid]/layout.tsx`
- Create: `frontend/app/projects/[pid]/scenes/page.tsx`
- Create: `frontend/components/SceneCard.tsx`
- Create: `frontend/components/SceneEditorModal.tsx`

- [ ] **Step 1: 写 `frontend/app/projects/[pid]/layout.tsx`**

```tsx
"use client";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { pid } = useParams<{ pid: string }>();
  const path = usePathname();
  const { data: project } = useSWR(pid ? `project-${pid}` : null,
    () => api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const isSku = path?.includes("/skus");
  const isScene = path?.includes("/scenes");

  return (
    <main className="max-w-6xl mx-auto p-4">
      <header className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3">
        <h1 className="text-lg font-bold">img2ec</h1>
        <span className="text-xs opacity-60">
          <Link href="/projects" className="text-blue-400 hover:underline">项目</Link>
          {project && <> / <strong className="text-zinc-100">{project.name}</strong></>}
        </span>
        <div className="flex-1" />
        <Link href={`/projects/${pid}/skus`}
          className={`px-3 py-1.5 text-xs rounded ${isSku ? "bg-blue-600 text-white" : "opacity-60 hover:opacity-100"}`}>SKU</Link>
        <Link href={`/projects/${pid}/scenes`}
          className={`px-3 py-1.5 text-xs rounded ${isScene ? "bg-blue-600 text-white" : "opacity-60 hover:opacity-100"}`}>场景库</Link>
      </header>
      {children}
    </main>
  );
}
```

- [ ] **Step 2: 写 `frontend/components/SceneCard.tsx`**

```tsx
import type { Scene } from "@/lib/types";

export function SceneCard({ scene, onClick }: { scene: Scene; onClick?: () => void }) {
  return (
    <div onClick={onClick}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-2 cursor-pointer transition">
      <div className="w-full h-28 bg-gradient-to-br from-amber-200 to-amber-900 rounded mb-2 relative flex items-center justify-center">
        <span className="absolute top-1.5 left-1.5 bg-black/55 text-white text-[10px] px-1.5 py-0.5 rounded">
          {scene.category}
        </span>
        <div className="w-1/2 h-1/2 bg-white/70 rounded shadow-md" />
      </div>
      <h3 className="text-xs font-semibold">{scene.name}</h3>
      <p className="text-[10px] opacity-55 line-clamp-2">{scene.desc || scene.prompt.slice(0, 60)}</p>
    </div>
  );
}
```

- [ ] **Step 3: 写 `frontend/components/SceneEditorModal.tsx`**

```tsx
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";

export function SceneEditorModal({
  pid, scene, onClose, onSaved,
}: { pid: string; scene: Scene | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: "", category: "自定义", desc: "", prompt: "", negative_prompt: "",
    ip_adapter_weight: 60, base_model: "flux-dev-fp8",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (scene) setForm({ ...form,
      name: scene.name, category: scene.category, desc: scene.desc,
      prompt: scene.prompt, negative_prompt: scene.negative_prompt,
      ip_adapter_weight: scene.ip_adapter_weight, base_model: scene.base_model,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene]);

  const submit = async () => {
    if (!form.name.trim() || !form.prompt.trim()) return setErr("场景名和 prompt 必填");
    setBusy(true);
    try {
      if (scene) await api.updateScene(pid, scene.id, form);
      else await api.createScene(pid, form);
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!scene) return;
    if (!confirm(`确认删除场景"${scene.name}"？`)) return;
    await api.deleteScene(pid, scene.id);
    onSaved();
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[520px] max-w-[700px] max-h-[90vh] overflow-y-auto"
           onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">{scene ? "编辑场景" : "新建场景"}</h2>
        {[
          { k: "name", label: "场景名", type: "input" },
          { k: "category", label: "品类（标签）", type: "input" },
          { k: "desc", label: "用途说明", type: "input" },
          { k: "prompt", label: "主 Prompt（英文）", type: "textarea" },
          { k: "negative_prompt", label: "负面 Prompt（可选）", type: "textarea" },
        ].map(f => (
          <div key={f.k} className="mb-3">
            <label className="text-xs opacity-65 block mb-1">{f.label}</label>
            {f.type === "textarea" ? (
              <textarea value={(form as any)[f.k]} onChange={e => setForm({ ...form, [f.k]: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" rows={3} />
            ) : (
              <input value={(form as any)[f.k]} onChange={e => setForm({ ...form, [f.k]: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" />
            )}
          </div>
        ))}
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">IPAdapter 权重：{form.ip_adapter_weight}</label>
          <input type="range" min={0} max={100} value={form.ip_adapter_weight}
            onChange={e => setForm({ ...form, ip_adapter_weight: +e.target.value })} className="w-full" />
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end items-center">
          {scene && <button className="text-red-400 border border-red-400 px-3 py-1 rounded text-xs" onClick={del}>删除</button>}
          <div className="flex-1" />
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>{busy ? "保存中…" : "保存"}</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 写 `frontend/app/projects/[pid]/scenes/page.tsx`**

```tsx
"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { SceneCard } from "@/components/SceneCard";
import { SceneEditorModal } from "@/components/SceneEditorModal";
import type { Scene } from "@/lib/types";

export default function ScenesPage() {
  const { pid } = useParams<{ pid: string }>();
  const { data: scenes, mutate } = useSWR(pid ? `scenes-${pid}` : null, () => api.listScenes(pid));
  const [editing, setEditing] = useState<Scene | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <>
      <div className="flex justify-end mb-3">
        <button onClick={() => setCreating(true)}
          className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">+ 新建场景</button>
      </div>
      {scenes && scenes.length === 0 && <p className="opacity-60 text-center py-12">还没场景，点右上新建</p>}
      <div className="grid grid-cols-4 gap-3">
        {scenes?.map(sc => <SceneCard key={sc.id} scene={sc} onClick={() => setEditing(sc)} />)}
      </div>
      {(editing || creating) && (
        <SceneEditorModal pid={pid} scene={editing}
          onClose={() => { setEditing(null); setCreating(false); }}
          onSaved={() => { setEditing(null); setCreating(false); mutate(); }} />
      )}
    </>
  );
}
```

- [ ] **Step 5: 手测**

启动后端前端，访问任意项目 → 点"场景库"Tab → 看到默认场景 → 点击编辑 / 新建。

Expected: CRUD 完整工作

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(frontend): add scenes library with CRUD modal"
```

---

## Task 15: 前端：SKU 列表 + 路径栏 + 新建 SKU

**Files:**
- Create: `frontend/components/PathBar.tsx`
- Create: `frontend/components/StatusPill.tsx`
- Create: `frontend/components/SkuRow.tsx`
- Create: `frontend/components/NewSkuModal.tsx`
- Create: `frontend/app/projects/[pid]/skus/page.tsx`

- [ ] **Step 1: 写 `frontend/components/PathBar.tsx`**

```tsx
"use client";
import { api } from "@/lib/api";

export function PathBar({ path, label = "目录" }: { path: string; label?: string }) {
  const onReveal = () => api.reveal(path);
  const onCopy = () => navigator.clipboard?.writeText(path);

  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      <span className="opacity-55">📂 {label}：</span>
      <code className="font-mono bg-zinc-950 px-2 py-0.5 rounded text-zinc-400">{path}/</code>
      <button onClick={onReveal} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">在 Finder 中显示</button>
      <button onClick={onCopy} className="px-2 py-0.5 border border-zinc-700 rounded text-[11px] hover:text-zinc-100">复制路径</button>
    </div>
  );
}
```

- [ ] **Step 2: 写 `frontend/components/StatusPill.tsx`**

```tsx
import type { SKUStatus, ImageStatus } from "@/lib/types";

const labels: Record<string, string> = {
  draft: "编辑中", ready: "待处理", running: "处理中",
  done: "已完成", error: "部分失败",
  pending: "排队", cutting: "抠图中", generating: "生 master 中",
  composing: "派生中", failed: "失败",
};

const styles: Record<string, string> = {
  draft: "bg-zinc-700 text-zinc-300",
  ready: "bg-blue-900/50 text-blue-300",
  pending: "bg-blue-900/50 text-blue-300",
  running: "bg-amber-900/50 text-amber-300",
  cutting: "bg-amber-900/50 text-amber-300",
  generating: "bg-amber-900/50 text-amber-300",
  composing: "bg-amber-900/50 text-amber-300",
  done: "bg-green-900/50 text-green-300",
  error: "bg-red-900/50 text-red-300",
  failed: "bg-red-900/50 text-red-300",
};

export function StatusPill({ status }: { status: SKUStatus | ImageStatus }) {
  return <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${styles[status]}`}>{labels[status]}</span>;
}
```

- [ ] **Step 3: 写 `frontend/components/SkuRow.tsx`**

```tsx
import Link from "next/link";
import type { SKU } from "@/lib/types";
import { StatusPill } from "./StatusPill";

export function SkuRow({ sku, sceneName }: { sku: SKU; sceneName: string }) {
  const total = sku.images.length;
  const done = sku.images.filter(i => i.status === "done").length;
  const meta =
    sku.status === "running" ? `${done}/${total} 已完成` :
    sku.status === "done" ? `${total * 4} 张输出（4 平台）` :
    sku.status === "error" ? `${done}/${total} 成功，可重试` :
    `${total} 张原图 / 场景：${sceneName}`;

  return (
    <Link href={`/projects/${sku.project_id}/skus/${sku.id}`}
      className="bg-zinc-900 border border-zinc-700 hover:border-blue-500 rounded-xl p-3 mb-2 flex items-center gap-3 cursor-pointer transition">
      <div className="w-14 h-14 bg-gradient-to-br from-zinc-700 to-zinc-900 rounded flex items-center justify-center text-xs opacity-60">
        {total} 图
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold mb-1">{sku.name}</div>
        <div className="text-xs opacity-60 flex gap-2 items-center">
          <StatusPill status={sku.status} />
          <span>{meta}</span>
        </div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: 写 `frontend/components/NewSkuModal.tsx`**

```tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Scene } from "@/lib/types";

export function NewSkuModal({
  pid, scenes, onClose, onCreated,
}: { pid: string; scenes: Scene[]; onClose: () => void; onCreated: (sid: string) => void }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sceneId, setSceneId] = useState(scenes[0]?.id ?? "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) return setErr("SKU 名必填");
    if (!sceneId) return setErr("请选场景");
    if (files.length === 0) return setErr("请选至少一张原图");
    setBusy(true);
    try {
      const sku = await api.createSku(pid, { name: name.trim(), scene_id: sceneId });
      for (const f of files) {
        await api.uploadImage(pid, sku.id, f);
      }
      onCreated(sku.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 min-w-[520px] max-w-[700px]" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-4">新建 SKU</h2>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">SKU 名</label>
          <input value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm" placeholder="例如：蓝色保温杯 500ml" autoFocus />
        </div>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">原图（可多张）</label>
          <input type="file" accept="image/*" multiple
            onChange={e => setFiles(Array.from(e.target.files || []))}
            className="text-xs" />
          {files.length > 0 && <p className="text-xs opacity-60 mt-1">{files.length} 张已选</p>}
        </div>
        <div className="mb-3">
          <label className="text-xs opacity-65 block mb-1">场景</label>
          <select value={sceneId} onChange={e => setSceneId(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm">
            {scenes.map(sc => <option key={sc.id} value={sc.id}>{sc.name}（{sc.category}）</option>)}
          </select>
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button className="px-3 py-2 text-sm border border-zinc-700 rounded" onClick={onClose}>取消</button>
          <button className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold disabled:opacity-50"
            onClick={submit} disabled={busy}>{busy ? "创建中…" : "创建并开始处理"}</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 写 `frontend/app/projects/[pid]/skus/page.tsx`**

```tsx
"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { SkuRow } from "@/components/SkuRow";
import { NewSkuModal } from "@/components/NewSkuModal";

export default function SkusPage() {
  const { pid } = useParams<{ pid: string }>();
  const router = useRouter();
  const { data: project } = useSWR(`project-${pid}`, () =>
    api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const { data: skus, mutate } = useSWR(`skus-${pid}`, () => api.listSkus(pid));
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));
  const [showNew, setShowNew] = useState(false);

  const sceneNameById = (id: string | null) =>
    scenes?.find(s => s.id === id)?.name ?? "未选";

  return (
    <>
      {project && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 mb-3 flex justify-between items-center gap-3">
          <PathBar path={project.root_path} label="项目目录（本地）" />
          <button onClick={() => setShowNew(true)}
            className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold whitespace-nowrap">+ 新建 SKU</button>
        </div>
      )}
      {skus && skus.length === 0 && <p className="text-center opacity-60 py-12">还没 SKU</p>}
      {skus?.map(s => <SkuRow key={s.id} sku={s} sceneName={sceneNameById(s.scene_id)} />)}
      {showNew && project && scenes && (
        <NewSkuModal pid={pid} scenes={scenes}
          onClose={() => setShowNew(false)}
          onCreated={async (sid) => {
            await api.processSku(pid, sid);
            mutate();
            router.push(`/projects/${pid}/skus/${sid}`);
          }} />
      )}
    </>
  );
}
```

- [ ] **Step 6: 手测**

进入项目 → 看到顶部项目目录条 + "新建 SKU" → 点击 → 填名字、选图、选场景 → 创建 → 自动调 process → 跳转到 SKU 详情（下个 task 实现）

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(frontend): add SKU list, path bar, status pills, new SKU modal"
```

---

## Task 16: 前端：SKU 详情 + 处理状态轮询 + 下载

**Files:**
- Create: `frontend/app/projects/[pid]/skus/[sid]/page.tsx`

- [ ] **Step 1: 写 `frontend/app/projects/[pid]/skus/[sid]/page.tsx`**

```tsx
"use client";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { PathBar } from "@/components/PathBar";
import { StatusPill } from "@/components/StatusPill";

export default function SkuDetailPage() {
  const { pid, sid } = useParams<{ pid: string; sid: string }>();
  const router = useRouter();
  const { data: sku, mutate } = useSWR(
    sid ? `sku-${sid}` : null,
    () => api.getSku(pid, sid),
    { refreshInterval: 2000 } // 处理中每 2s 轮询；完成后停止
  );
  const { data: project } = useSWR(`project-${pid}`, () =>
    api.listProjects().then(ps => ps.find(p => p.id === pid)));
  const { data: scenes } = useSWR(`scenes-${pid}`, () => api.listScenes(pid));

  if (!sku) return <p className="opacity-60">加载中…</p>;
  const scene = scenes?.find(s => s.id === sku.scene_id);
  const skuPath = project ? `${project.root_path}/${sku.name}` : "";

  const onProcess = async () => { await api.processSku(pid, sid); mutate(); };
  const onDelete = async () => {
    if (!confirm(`删除 SKU "${sku.name}"？`)) return;
    await api.deleteSku(pid, sid);
    router.push(`/projects/${pid}/skus`);
  };

  return (
    <div>
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 mb-3">
        <div className="flex items-center gap-3 mb-2">
          <strong className="text-base">{sku.name}</strong>
          <StatusPill status={sku.status} />
          <div className="flex-1" />
          {sku.status === "ready" && <button onClick={onProcess} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">▶ 开始处理</button>}
          {sku.status === "running" && <span className="text-sm opacity-60">⏳ 处理中…</span>}
          {sku.status === "done" && <a href={api.downloadSku(sku.id)} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">⬇ 一键下载 zip</a>}
          {sku.status === "error" && <button onClick={onProcess} className="px-3 py-2 text-sm bg-blue-600 rounded font-semibold">▶ 重试失败项</button>}
          <button onClick={onDelete} className="text-red-400 border border-red-400 rounded px-2 py-1 text-xs">删除</button>
        </div>
        <PathBar path={skuPath} label="SKU 目录" />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <h3 className="text-xs uppercase opacity-50 mb-2">原图（{sku.images.length} 张）</h3>
          {sku.images.map(img => (
            <div key={img.id} className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2 flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-zinc-600 to-zinc-900 rounded flex items-center justify-center text-[10px] opacity-70">
                {img.name.slice(0, 4)}
              </div>
              <div className="flex-1">
                <div className="text-xs">{img.name}</div>
                <div className="text-[11px] opacity-55 mt-1 flex items-center gap-2">
                  <StatusPill status={img.status} />
                  {img.status === "done" && <span>· 输出 4 张</span>}
                  {img.err_msg && <span>· {img.err_msg}</span>}
                </div>
                {["cutting", "generating", "composing"].includes(img.status) && (
                  <div className="h-1 bg-zinc-800 rounded mt-1.5 overflow-hidden">
                    <div className="h-full bg-amber-500 transition-all" style={{ width: `${img.progress}%` }} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div>
          <div className="bg-zinc-900 border border-zinc-700 rounded p-3 mb-2 text-xs">
            <div className="opacity-50 uppercase mb-2">场景模板</div>
            {scene ? (
              <>
                <div className="font-semibold">{scene.name}</div>
                <div className="opacity-55 mt-1">{scene.category}</div>
                <div className="opacity-55 mt-2 line-clamp-3">{scene.prompt}</div>
              </>
            ) : <div>未设置</div>}
          </div>
          <div className="bg-zinc-900 border border-zinc-700 rounded p-3 text-xs">
            <div className="opacity-50 uppercase mb-2">输出平台</div>
            <div>✓ 抖店　✓ 视频号　✓ 淘宝　✓ 小红书</div>
            <div className="opacity-55 mt-2">MVP：每平台 1:1 主图 1 张</div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 启动 Celery worker**

```bash
cd backend
source .venv/bin/activate
celery -A img2ec.celery_app worker --loglevel=info
```

Expected: worker 连上 Redis，待命

- [ ] **Step 3: 端到端 smoke 测试（手动）**

1. 启动 backend：`uvicorn img2ec.main:app --reload --port 8000`
2. 启动 celery worker（上面 step 2）
3. 启动 frontend：`npm run dev`
4. ComfyUI 必须在 gpu box 已经装好 workflow（用真实 workflow 替换 `workflows/generate_master_1x1.json`）
5. 浏览器：建项目（带默认场景）→ 上传一张原图建 SKU → 点开始处理
6. 等待几十秒（rembg 抠图 + ComfyUI 生图）
7. 详情页应显示 done，4 张派生图在 `~/img2ec/projects/<project>/<sku>/outputs/{douyin,shipinhao,taobao,xiaohongshu}/`
8. 点"一键下载 zip" → 拿到 zip 文件
9. 点"在 Finder 中显示" → mac 自动打开访达

Expected: 全程跑通

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(frontend): add SKU detail page with polling, processing, download"
```

---

## Task 17: 端到端集成测试 + smoke 验收

**Files:**
- Create: `backend/tests/test_e2e/test_pipeline_e2e.py`
- Create: `backend/tests/test_e2e/conftest.py`

- [ ] **Step 1: 写 `backend/tests/test_e2e/conftest.py`**

```python
"""E2E 测试用 mock ComfyUI（不依赖 gpu box）。"""
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image


@pytest.fixture
def mock_comfy(monkeypatch, tmp_path):
    """Mock ComfyClient：跳过真实 HTTP，直接生成一张占位 1:1 master。"""
    def fake_generate(*, output_path, **_):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1500, 1500), (200, 100, 50))
        img.save(output_path, quality=92)
        return Path(output_path)

    monkeypatch.setattr("img2ec.core.pipeline.generate_master_1x1", fake_generate)
    yield
```

- [ ] **Step 2: 写 `backend/tests/test_e2e/test_pipeline_e2e.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from img2ec.core.pipeline import process_one_image


def test_e2e_pipeline_with_white_bg(tmp_path, fixtures_dir, mock_comfy):
    sku_d = tmp_path / "sku"
    sku_d.mkdir()

    derived = process_one_image(
        src_path=fixtures_dir / "white_bg.jpg",
        sku_dir=sku_d,
        image_stem="front",
        scene_prompt="on white marble, warm light",
        scene_neg="cluttered",
        ip_weight=60,
        seed=42,
        comfy_client=MagicMock(),
        workflow_path=Path("workflows/generate_master_1x1.json"),
    )

    assert set(derived.keys()) == {"douyin", "shipinhao", "taobao", "xiaohongshu"}
    for path in derived.values():
        assert path.exists()
        with Image.open(path) as img:
            assert img.size in [(1080, 1080), (800, 800)]


def test_e2e_pipeline_with_photo_bg_runs_cutout(tmp_path, fixtures_dir, mock_comfy):
    sku_d = tmp_path / "sku"
    sku_d.mkdir()

    derived = process_one_image(
        src_path=fixtures_dir / "photo_bg.jpg",
        sku_dir=sku_d,
        image_stem="side",
        scene_prompt="on marble",
        scene_neg="cluttered",
        ip_weight=60,
        seed=42,
        comfy_client=MagicMock(),
        workflow_path=Path("workflows/generate_master_1x1.json"),
    )

    # cutout/ 目录下应有抠图结果
    assert (sku_d / "cutout" / "side.png").exists()
    assert len(derived) == 4
```

- [ ] **Step 3: 跑 E2E 测试**

```bash
cd backend
pytest tests/test_e2e -v
```

Expected: 2 passed（首次会 rembg 加载模型，30-60s）

- [ ] **Step 4: 跑全部测试统计覆盖率**

```bash
pytest --cov=img2ec --cov-report=term-missing
```

Expected: 总覆盖率 ≥ 75%；核心模块（pipeline、derive、bg_detect）≥ 90%

- [ ] **Step 5: 验收 checklist**

人工逐项核对（在工程师本地跑过）：

- [ ] 首页能创建项目，新项目自带 1 个默认场景"大理石台·暖光"
- [ ] 项目内可以打开"场景库"Tab，编辑/新建/删除场景
- [ ] 新建 SKU 时可上传多张图，选场景，提交后跳详情页
- [ ] SKU 详情页显示 SKU 路径，点"在 Finder 中显示"会打开访达定位到 SKU 目录
- [ ] 处理流水线：white_bg.jpg 跳过 rembg；photo_bg.jpg 走 rembg
- [ ] ComfyUI 调用成功，master 落 `<sku>/master/<stem>-1x1.jpg`
- [ ] 派生输出 4 张 1:1 主图，分别 1080² / 800² / 800² / 1080²
- [ ] 完成后状态为 done，"一键下载 zip"能下载到含 4 个平台目录的 zip
- [ ] 浏览器刷新 SKU 详情，状态从后端正确恢复（不丢）
- [ ] 关闭浏览器再打开，处理仍在后端进行（如果中途的话）

- [ ] **Step 6: Commit & tag MVP**

```bash
git add -A
git commit -m "test: add E2E pipeline tests with mocked ComfyUI"
git tag v0.1.0-mvp
```

---

## Self-Review Checklist

After implementing all tasks, verify against spec:

- [ ] §3.3 派生表 1:1 行：4 平台 main 图都有（Task 9 的 `PLATFORMS_1X1_SIZES`）
- [ ] §4.3 MVP 内置 1 场景（Task 3）
- [ ] §5.1 数据模型 4 张表（Task 2）
- [ ] §5.2 SKU/Image 状态机（Task 2 + Task 10 状态聚合）
- [ ] §6 数据流 step 1-7（Task 5/6/8/9/10 + Task 12 process API）
- [ ] §8 文件系统布局：`source/`、`cutout/`、`master/`、`outputs/<platform>/`（Task 4 + Task 12）
- [ ] §9.1 后端模块 11 个 .py 文件全部就位
- [ ] §9.2 前端 5 个页面 + 6 个组件（Task 13-16）
- [ ] §10.2 失败到 image 级，可重试（Task 10 task + Task 12 process 复用 pending+failed 过滤）
- [ ] §11.1 SQLite 单一真相源（Task 2）
- [ ] §11.3 浏览器刷新无感（Task 16 SWR 轮询）
- [ ] §13.2 路径透出 + Finder 集成（Task 4 + Task 13/15/16）

不在 MVP 范围（在 Phase 2/3/4，明确不做）：
- 详情页拼图叠字、5 master 全量、LLM 字段生成（Phase 2）
- SSE 事件流（Phase 3 — MVP 用 SWR 轮询替代）
- EventBus + n8n（Phase 3）
- 增量处理 / 追加图后只跑新增（Phase 3）
- 插件化 pipeline、watchdog 输入源（Phase 4）

---

## 后续步骤

完成 Task 1-17 后，跑 `pytest && cd ../frontend && npm run build` 全绿即 MVP 完成。下一步：

1. **Phase 2 plan**：写 `2026-MM-DD-img2ec-phase2.md`，扩展 5 master + 详情页拼图 + LLM 字段生成 + 16 默认场景
2. **Phase 3 plan**：EventBus + n8n + SSE + 增量处理
3. **gpu box ComfyUI 配置文档**：单独写 `docs/comfyui-setup.md`，列模型权重清单和 workflow 搭建步骤（不在本 plan 范围内，因为不写代码）
