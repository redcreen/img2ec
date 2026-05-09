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

## IPAdapter 待修（Phase 1.5）

目标：让商品 cutout 真正注入到生成结果中，而不是只跑 prompt。

**Workflow** 已写好骨架：`workflow_master_with_ipadapter_reference.json`（在 gpu box 上）。结构：
```
LoadImage(__CUTOUT__) → ApplyIPAdapterFlux(weight=__IP_WEIGHT__)
                        ↑
IPAdapterFluxLoader(flux-ip-adapter-instantx.bin, siglip-so400m-patch14-384)
   ↑ ↑
   被这步阻塞：120s 内 siglip clip_vision 加载没完成（首次加载 3GB+ siglip 模型 + 处理器配置可能慢）
```

**修法可能**：
1. **延长测试 timeout 到 5 分钟**重试一次（可能是单次首次加载慢，后续会快）
2. **确认 siglip 处理器配置文件**已在 `~/.cache/huggingface/hub/models--google--siglip-so400m-patch14-384/` 下，缺则运行：
   ```cmd
   D:\AI\ComfyUI_windows_portable\python_embeded\python.exe -c "from transformers import AutoProcessor; AutoProcessor.from_pretrained('google/siglip-so400m-patch14-384')"
   ```
3. **检查 IPAdapterFluxLoader 节点是否接受 HF id 字符串还是只接受本地路径**。可能需要把 `clip_vision` 字段改为本地相对路径（`"models/clip_vision/siglip-so400m-patch14-384.safetensors"`）+ 在 ComfyUI 的 `extra_model_paths.yaml` 配置 siglip。

接通后：
- 把 mac 端 `backend/workflows/generate_master_1x1.json` 替换为 IPAdapter 版本
- 修改 `master_gen.py`：把 `ip_weight=ip_weight`（0-100）改为 `ip_weight=ip_weight / 100`（0.0-1.0），匹配 Flux IPAdapter 标准
- 重跑 smoke

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
