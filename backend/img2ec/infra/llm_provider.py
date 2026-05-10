"""LLMProvider 抽象 + CodexCLIProvider 实现（subprocess `codex exec`）。"""
from __future__ import annotations

import json
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


class LLMProviderError(RuntimeError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate_structured(
        self,
        *,
        prompt: str,
        json_schema: dict,
        image_path: Path | None = None,
        timeout: int = 180,
    ) -> dict:
        """根据 prompt（含可选 image）生成符合 json_schema 的结构化 JSON。

        Returns: 解析后的 dict，已由 schema 严格校验。
        Raises: LLMProviderError on failure.
        """


class CodexCLIProvider(LLMProvider):
    """通过 `codex exec` subprocess 调用 OpenAI Codex CLI。

    需要：
      - 已 `codex login`
      - codex CLI ≥ 0.129
    """

    def __init__(self, codex_bin: str = "codex"):
        self.codex_bin = codex_bin

    def generate_structured(
        self,
        *,
        prompt: str,
        json_schema: dict,
        image_path: Path | None = None,
        timeout: int = 180,
    ) -> dict:
        with tempfile.TemporaryDirectory() as td:
            schema_file = Path(td) / "schema.json"
            output_file = Path(td) / "output.json"
            schema_file.write_text(json.dumps(json_schema), encoding="utf-8")

            cmd = [
                self.codex_bin, "exec", "-",
                "--ephemeral",
                "--skip-git-repo-check",
                "--output-schema", str(schema_file),
                "-o", str(output_file),
            ]
            if image_path is not None:
                cmd.extend(["-i", str(image_path)])

            try:
                result = subprocess.run(
                    cmd,
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as e:
                raise LLMProviderError(f"codex exec timed out after {timeout}s") from e

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
                raise LLMProviderError(f"codex exec rc={result.returncode}: {stderr}")

            if not output_file.exists():
                raise LLMProviderError("codex exec produced no output file")

            try:
                return json.loads(output_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raw = output_file.read_text(encoding="utf-8")[:500]
                raise LLMProviderError(f"invalid JSON output: {e}; raw[:500]={raw!r}") from e
