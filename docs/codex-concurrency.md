# Codex CLI 并发隔离：跨任务图片污染问题与解决方案

> **TL;DR**：`codex exec` 把生成图写到 **全局共享目录** `~/.codex/generated_images/`。
> 并发调用时（不论是本进程的多个 worker，还是本机任何其他用 Codex 的应用），
> 老代码 `rglob` 整个目录抓"最新 PNG"会**抢到别人的图**。
> 解决：每次调用用独立 `CODEX_HOME=<tempdir>`，物理隔离输出目录。

## 1. 问题症状

用户多次报告："新生成的 master 里混入了我别的应用 / 别的项目的图"。具体表现：

- A SKU 的 `master/<stem>-9x16.jpg` 内容明显不是该产品
- 同一文件名在另一个 SKU 目录下也存在但 MD5 不同（说明文件路径已物理隔离）
- 推 broker 给 Codex 的 prompt 是对的，问题不在 prompt 端

**关键线索**：用户机子上同时跑着 Claude Code、其他 Codex 客户端、本项目 worker 等多个进程。

## 2. 根本原因

### 2.1 Codex CLI 的输出布局

```
~/.codex/generated_images/
├── <session-uuid-1>/
│   └── ig_xxxxxxxx.png
├── <session-uuid-2>/
│   └── ig_yyyyyyyy.png
└── ... 累积上千个子目录从不清理
```

- 每次 `codex exec --ephemeral` 创建一个新 session 子目录
- 所有 codex 实例（不论是哪个项目 / 哪个 caller）都写到同一个 `~/.codex/generated_images/`
- 子目录从不自动清理（用户机上有 1000+ 累积 session）

### 2.2 老代码的 race condition

之前 `_run_codex_to_image` 做的：

```python
before_ts = time.time()
subprocess.run(["codex", "exec", "-", "--ephemeral", ...])

# ❌ rglob 整个全局目录 — 抓到任何人的 PNG
candidates = [p for p in CODEX_IMG_DIR.rglob("*.png")
              if p.stat().st_mtime >= before_ts - 1]
newest = max(candidates, key=lambda p: p.stat().st_mtime)
```

**失败场景**：
1. Worker A 调用 codex，记下 `before_ts_A`
2. Worker B 同时也在调用 codex，先完成、写出 png
3. Worker A 的 codex 也完成
4. Worker A 跑 rglob → 看到 A 和 B 两张 png，按 mtime 取最新
5. 如果 B 的 png 略晚 → **A 拿到了 B 的图**

中间尝试过 "snapshot session subdirs before / after"，但仍有窗口：
- A 的 `sessions_before` 不包含 B 的 session
- A 跑期间，B 的 session 出现了
- A 的 `sessions_after - sessions_before` 包含 B 的 session
- A 选 newest 时还是可能选到 B

并发条件下，**任何依赖"扫共享目录"的方法都有 race**。

## 3. 解决方案：Per-call 隔离 CODEX_HOME

### 3.1 思路

利用 Codex 支持的 `CODEX_HOME` 环境变量：

- 每次调用用 `tempfile.TemporaryDirectory` 创建唯一目录
- 把真实 `~/.codex/` 里的 **auth + config + agent 上下文** 用 **symlink** 暴露到 temp 目录
- subprocess env 设 `CODEX_HOME=<temp>`
- codex 把图写到 `<temp>/generated_images/<session>/ig_*.png` —— **该目录只有本次调用能访问**
- 跑完直接从 `<temp>/generated_images/` 取唯一 PNG，物理上不可能拿到别人的
- 退出 `with` 块自动清理 temp 目录

### 3.2 关键代码

位置：`backend/img2ec/infra/codex_image.py`

```python
ISOLATED_HOMES_ROOT = Path("/tmp/img2ec-codex")
_LINKED_FILES = ("auth.json", "config.toml", "AGENTS.md", "hooks.json")
_LINKED_DIRS  = ("bin",)

@contextmanager
def _isolated_codex_home():
    real = Path.home() / ".codex"
    ISOLATED_HOMES_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="home-", dir=str(ISOLATED_HOMES_ROOT)) as td:
        tmp = Path(td)
        for name in _LINKED_FILES:
            src = real / name
            if src.exists():
                (tmp / name).symlink_to(src)
        for name in _LINKED_DIRS:
            src = real / name
            if src.exists():
                (tmp / name).symlink_to(src, target_is_directory=True)
        yield tmp

def _run_codex_to_image(...):
    with _isolated_codex_home() as home:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        proc = subprocess.run([...], env=env, ...)
        # 本次专属目录 — 不会有任何其他来源的图
        img_dir = home / "generated_images"
        candidates = list(img_dir.rglob("*.png"))
        newest = max(candidates, key=lambda p: p.stat().st_mtime)
        ...
```

### 3.3 为什么 symlink 能让 auth 工作

Codex 启动时按 `$CODEX_HOME/auth.json` 等路径读文件。symlink 是透明的——`open()` 调用解引用到真实文件，Codex 完全感知不到。**只有写入新文件**（如 generated_images）才会落到 temp dir 里。

### 3.4 并发安全证明

| 假设的攻击 | 现在的结果 |
|---|---|
| 另一个 Codex 客户端写 `~/.codex/generated_images/` | 不影响本调用（我们读的是 temp dir，不是 ~/.codex） |
| 本进程的另一个 worker 同时跑 | 各自 temp dir，物理隔离 |
| 我把 codex 中断 / 进程被 kill | tempdir 退出自清；万一泄漏，下条兜底 |

## 4. 残留目录清理（兜底）

`SIGKILL` / OOM / 进程崩溃会导致 tempdir 泄漏（Python 的 `__exit__` 没机会跑）。

兜底机制：固定 tempdir 父目录为 `/tmp/img2ec-codex/`，加 cleanup 函数：

```python
def cleanup_orphan_codex_homes(max_age_seconds: int = 3600) -> int:
    """删超过 max_age 的孤儿目录。"""
```

两处触发：
- `celery_app.py`: `@worker_ready` signal → worker 启动时清
- `main.py`: FastAPI `@app.on_event("startup")` → uvicorn 启动时清

正常路径 → 5–60s 内自清。孤儿 → 下次 worker/uvicorn 重启时 1 小时门限清掉。**最坏情况累积时长 = 重启间隔时长**。

容量估算：4 worker × 每张 ~3MB × 同时最多 4 个 active → ~12MB 上限。

## 5. 验证 & 监控

### 启动看 worker 是否清了 orphan
```bash
grep "cleaned.*orphan" .logs/dev-worker.log
# [img2ec] cleaned 3 orphan codex home dirs on worker boot
```

### 实时看 active home
```bash
ls /tmp/img2ec-codex/          # 应该 ≤ celery worker concurrency
du -sh /tmp/img2ec-codex/      # 总占盘
```

### 排查疑似串图
```bash
# 1. 看文件 mtime 对不上的话基本是历史污染
stat -f "%Sm %z bytes" <path>

# 2. 同 stem 跨 SKU 的 MD5 必须不同 — 否则是路径串
md5 <sku-A>/master/<stem>-<ratio>.jpg
md5 <sku-B>/master/<stem>-<ratio>.jpg
```

## 6. 给其他 session / feature 开发者的提醒

如果你要新增一个调 Codex CLI 的功能，**务必走 `_run_codex_to_image` 或 `codex_text`**（都已经接了隔离 home），**不要**：

- ❌ 直接 `subprocess.run(["codex", ...])`（会用全局 ~/.codex/，跟其他人抢图）
- ❌ 把 `CODEX_IMG_DIR` 当输出源扫
- ❌ 把 `~/.codex/generated_images/` 当读取入口

如果调用模式不一样（比如不是出图、是别的 codex 功能），需要文本输出就用现成的 `codex_text()`；
要扩展新的 codex 调用方式，**先把它包装在 `_isolated_codex_home()` 里**，复用同一套隔离机制。

## 7. 历史背景 commit

- `4757277` fix(codex): isolated CODEX_HOME per call — eliminates cross-session image leakage
- 之前几个尝试：
  - `95f0751` 把 SKU 磁盘路径加 UUID 后缀（解决跨 SKU 串图，但没解决 Codex 共享目录问题）
  - 中间一版用 "before/after snapshot session dirs" 比对，并发下仍有 race
