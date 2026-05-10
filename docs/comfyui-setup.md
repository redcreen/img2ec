# ComfyUI Setup for img2ec

> Last updated: 2026-05-09 — Phase 1 baseline workflow validated end-to-end.

## 当前状态

✅ **已就绪并测通**：mac → gpu box ComfyUI 全链路（104s/图，首次加载；后续更快）

❌ **未接通**：IPAdapter Flux（`siglip` clip_vision 加载在 120s 内未完成；详情见下方 §"IPAdapter 待修"）

## gpu box 配置概要

| 项目 | 值 |
|---|---|
| 机器 | Windows 10/11，RTX 4080 SUPER 16GB |
| LAN IPv4 | `192.168.2.20` |
| ComfyUI 路径 | `D:\AI\ComfyUI_windows_portable` |
| ComfyUI 启动参数 | `--listen 0.0.0.0 --port 8188` |
| 防火墙 | 已开 inbound TCP 8188 (Private network) |
| 已装 custom nodes | `ComfyUI_IPAdapter_plus`, `ComfyUI-IPAdapter-Flux` |

## 模型清单

`D:\AI\ComfyUI_windows_portable\ComfyUI\models\` 下：

| 类别 | 文件 | 大小 | 用途 |
|---|---|---|---|
| checkpoints | `flux1-dev-fp8.safetensors` | 16 GB | 主底模（Flux dev FP8 一体版） |
| checkpoints | `RealVisXL_V5.0_fp16.safetensors`（symlink） | — | SDXL 备选 |
| checkpoints | `sd_xl_base_1.0.safetensors`（symlink） | — | SDXL 基线 |
| clip | `clip_l.safetensors` | 234 MB | Flux text encoder L |
| clip | `t5xxl_fp8_e4m3fn.safetensors` | 4.56 GB | Flux text encoder T5XXL |
| clip_vision | `siglip-so400m-patch14-384.safetensors` | 3.27 GB | IPAdapter Flux 用（待接） |
| clip_vision | `CLIP-ViT-H-14.safetensors`（symlink） | — | SDXL IPAdapter 用 |
| ipadapter | `ip-adapter-plus_sdxl_vit-h.safetensors` | — | SDXL 用 |
| ipadapter（flux） | `flux-ip-adapter-instantx.bin` | 5.03 GB | Flux 用（待接） |
| controlnet | `flux-controlnet-union-pro.safetensors` | 6.15 GB | Flux ControlNet（V2 用） |
| controlnet | `controlnet-union-sdxl-1.0-promax.safetensors` | — | SDXL ControlNet |
| vae | `sdxl_vae.safetensors` | — | SDXL VAE |
| vae | `taef1`（内置） | — | Flux 优化 VAE |

## Phase 1 baseline workflow

`backend/workflows/generate_master_1x1.json` — 9 节点，纯 prompt-driven Flux dev FP8：

```
CheckpointLoaderSimple(flux1-dev-fp8)
  ↓ MODEL/CLIP/VAE
DualCLIPLoader(clip_l + t5xxl_fp8) → CLIP
  ↓
CLIPTextEncodeFlux(__PROMPT__, guidance=3.5)  → positive
CLIPTextEncodeFlux(__NEG__, guidance=3.5)     → negative
EmptyFlux2LatentImage(1024×1024)              → empty latent
VAELoader(taef1)                              → VAE
KSampler(seed=__SEED__, euler, simple, 20 steps, cfg=7.5)
  ↓
VAEDecode → SaveImage(filename_prefix=img2ec_master)
```

**占位符**：
- `__PROMPT__` — 场景描述（来自 SceneTemplate.prompt）
- `__NEG__` — 负面提示（SceneTemplate.negative_prompt）
- `__SEED__` — 随机种子（master_gen 传 42 或随机）

**⚠️ 当前限制**：
- 商品 cutout 上传到 ComfyUI 的 `input/` 目录但**未被 workflow 使用** — 输出是 prompt 描述的纯场景图，**不含商品本身**
- 输出实际是 512×512（`EmptyFlux2LatentImage` 把 1024 当 latent 维度内部 halve；想 1024 输出需把宽高填 2048）
- 这个 workflow 用于验证 mac↔gpu 链路 wiring，**生产可用性等 IPAdapter 接通**

## 网络配置

mac 端 `backend/img2ec/config.py` 默认：
```python
comfy_url: str = "http://192.168.2.20:8188"
```

如果 gpu box LAN IP 变了，用 env 覆盖：
```bash
# backend/.env
IMG2EC_COMFY_URL=http://<新IP>:8188
```

或者 `export IMG2EC_COMFY_URL=...`。

## 启动 ComfyUI

gpu box 上：
```bat
D:\AI\ComfyUI_windows_portable\run_nvidia_gpu.bat
```

启动脚本里如果没有 `--listen 0.0.0.0`，加上：
```bat
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 0.0.0.0 --port 8188 %*
```

确认监听：
```powershell
netstat -an | findstr :8188
# 应看到 0.0.0.0:8188 LISTENING
```

mac 端 ping 测试：
```bash
curl http://192.168.2.20:8188/system_stats | jq .system.os
# 应返回 "win32"
```

## 端到端 smoke 测试

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_master_gen.py
```

预期：
- `[1/4]` 生成 test cutout
- `[2/4]` 连接 ComfyUI（system_stats 返回 win32）
- `[3/4]` 提交 workflow，~100s 出图（首次；后续 ~30s）
- `[4/4]` `/tmp/img2ec_smoke/smoke_master_1x1.png` 存在，size > 100KB

## IPAdapter Flux — ✅ 已修通（2026-05-10）

### 修法（已采纳）

gpu box 的 HuggingFace 网络问题用 mac 中转绕开：
1. mac（能上 HF）下载完整 `google/siglip-so400m-patch14-384` 仓库到 `/tmp/`
2. `model.safetensors` 与 gpu 上现有同名文件 MD5 一致，跳过传输
3. scp 6 个小文件（config / preprocessor / tokenizer / spiece / special tokens）到 `D:\Ai\ComfyUI_windows_portable\ComfyUI\models\clip_vision\siglip-so400m-patch14-384\`
4. 验证：`python_embeded\python.exe -c "AutoProcessor.from_pretrained(<local_path>, local_files_only=True)"` 返回 `SiglipProcessor`

### Mac 端代码改动

- `backend/workflows/generate_master_1x1.json` 替换为 IPAdapter 12-node 版本（含 `LoadImage` + `IPAdapterFluxLoader` + `ApplyIPAdapterFlux`）
- `backend/img2ec/core/master_gen.py`：`ip_weight=ip_weight / 100.0`（0-100 → 0.0-1.0）
- `backend/img2ec/core/master_gen.py`：新增 `_flatten_rgba_to_white_rgb()` — IPAdapter 不能很好处理透明 PNG，上传前把 RGBA cutout 拍平到白底 RGB

### 验证结果

`scripts/smoke_master_gen.py` 跑通：商品（瓶状物 RGBA cutout，flatten 后）输入 → IPAdapter 注入视觉特征 → prompt 驱动大理石场景 → 输出图含**可识别的商品** + **场景背景**。

**节点执行确认**（ComfyUI history）：
- node 6 `IPAdapterFluxLoader` ✓
- node 7 `ApplyIPAdapterFlux` ✓

### 调优方向（Phase 1.6+）

当前默认参数 (steps=20, cfg=7.5, scheduler=simple, IPAdapter weight=0.6) 输出有些发糊。可以试：
- 提高 steps 到 28-30
- 调 weight 到 0.4-0.5（让 prompt 更主导画面构图）
- 用更精细的 cutout（rembg 真实电商图比合成图效果好）
- 切到 `dpmpp_2m_sde` + `karras` 看看锐度

这些是产品化迭代，**不阻塞架构层**。

---

## IPAdapter 修通前的 BLOCKER 记录（保留供日后参考）

目标：让商品 cutout 真正注入到生成结果中，而不是只跑 prompt。

**Workflow 草稿已就位**：`workflow_master_ipadapter_v2.json`（在 gpu box 上）。结构与 baseline 相同，多两个节点：
```
LoadImage(__CUTOUT__) → ApplyIPAdapterFlux(weight=__IP_WEIGHT__)
                        ↑
IPAdapterFluxLoader(flux-ip-adapter-instantx.bin, "google/siglip-so400m-patch14-384")
```

### Blocker

`ComfyUI-IPAdapter-Flux` 自定义节点的 `IPAdapterFluxLoader` 在加载 siglip clip_vision 时调用 `transformers.AutoProcessor.from_pretrained("google/siglip-so400m-patch14-384")`。这个调用：

1. **优先尝试本地**：`models/clip_vision/siglip-so400m-patch14-384/` 目录里要有完整 HF 仓库文件结构（`config.json` + `preprocessor_config.json` + `tokenizer.json` + `special_tokens_map.json` + `model.safetensors` + 其它）
2. **失败回退到 HF Hub 下载**：但 gpu box 网络无法访问 huggingface.co（实测多次 timeout）

我们已有的 `siglip-so400m-patch14-384.safetensors`（3.27 GB）只是模型权重，缺所有配置/tokenizer JSON 文件。手动伪造 JSON 可工作但风险高。

### 修法（按可行性排序）

1. **解决网络**：让 gpu box 能 GET huggingface.co（VPN / 公司代理 / 镜像站）。一次下载完成后该模型永久缓存在 `~/.cache/huggingface/hub/`，后续不需要网。
2. **手动拷贝 HF 仓库**：从一台能上 HF 的机器（mac？）下载完整 `google/siglip-so400m-patch14-384` 仓库（小文件 + 大权重，~3.5 GB），rsync 到 gpu box 的 `~/.cache/huggingface/hub/models--google--siglip-so400m-patch14-384/`。
3. **方案切换**：放弃 IPAdapter，改用 ControlNet — 已有 `flux-controlnet-union-pro.safetensors`，但需要装 `comfyui_controlnet_aux` 提供 Canny 等预处理器（也需网络）。
4. **方案切换 2**：用 SDXL + 标准 IPAdapter Plus（`ip-adapter-plus_sdxl_vit-h.safetensors` + `CLIP-ViT-H-14`），SDXL 的 IPAdapter 走 ComfyUI 内置 clip_vision，**不依赖 HF transformers**。代价：底模换 SDXL，质量比 Flux 略差但生态稳定。

### 临时方案（已采纳，Phase 1 用）

baseline workflow 跑通 ComfyUI 集成链路，**不注入商品**。生成的 master 是按 prompt 描述的纯场景图。可以验证 mac↔gpu box 通信、文件 IO、Pillow 派生、API/UI 整体流程。

**生产可用性需要 IPAdapter 修通后才有**。当前 master 看起来像漂亮的场景图，但商品本身没参与生成 — 不是真正可发布的电商图。

### 接通后要改的

- `backend/workflows/generate_master_1x1.json` → 替换为 IPAdapter 版本（含 LoadImage + IPAdapterFluxLoader + ApplyIPAdapterFlux 节点）
- `backend/img2ec/core/master_gen.py`：`ip_weight=ip_weight` → `ip_weight=ip_weight / 100`（Flux IPAdapter weight 0.0-1.0）
- 重跑 `scripts/smoke_master_gen.py`，确认输出图含商品视觉特征

## 后期增强（Phase 2+）

- **ComfyUI-Manager** 装上方便运行时装节点（前次安装因网络超时失败，可以从 GitHub release 直接下 zip 解压到 `custom_nodes/`）
- **comfyui_controlnet_aux** 加 Canny preprocessor，让 ControlNet 锁住商品轮廓（V2 想要"商品轮廓 100% 准确"时用）
- **5 master 全量**：再做 4 个 workflow（750w long、3:4、9:16、16:9），或在一个 workflow 里多 KSampler 节点并行出 5 张
- **真正的商品参考图**：当前 cutout 是 RGBA 透明背景，可能 IPAdapter 喂得不好；可以先合成到白底再喂

## 故障排查

| 现象 | 可能原因 | 处置 |
|---|---|---|
| mac smoke 测试报 connection refused | gpu box 防火墙 / `--listen 0.0.0.0` 没生效 | 在 gpu box 上 `netstat -an \| findstr :8188` 看监听地址；不是 `0.0.0.0` 的话改启动脚本 |
| 出图非常慢（>180s） | 首次模型从硬盘加载到 VRAM；或 GPU 被别的进程占着 | `nvidia-smi` 看显存；首次预热完后续会快 |
| 出图分辨率不对（512 vs 1024） | `EmptyFlux2LatentImage` 节点把宽高当 latent 维度 | 想 1024 输出 → workflow 里改宽高为 2048 |
| 输出全是 0x0 黑图 | sampler / scheduler 与 Flux 不兼容 | 确认 `sampler_name: "euler"`, `scheduler: "simple"` |
| `IPAdapterFluxLoader` 报 siglip 加载错 | 见上方 §IPAdapter 待修 |
