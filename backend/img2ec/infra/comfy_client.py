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
        # ComfyUI 通常在 LAN，禁用 env proxy 检测避免 SOCKS proxy 等干扰
        self._client = httpx.Client(timeout=timeout, trust_env=False)

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
        from img2ec.infra.fs_layout import atomic_write_bytes
        atomic_write_bytes(resp.content, dst_path)

    def close(self) -> None:
        self._client.close()
