from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="IMG2EC_")

    db_url: str = "sqlite:///./img2ec.db"
    redis_url: str = "redis://localhost:6379/0"
    # ComfyUI HTTP API. SSH alias `gpu` is not DNS-resolvable; use the LAN IPv4 directly.
    # Override via IMG2EC_COMFY_URL env var or .env file if your gpu box has a different IP.
    comfy_url: str = "http://192.168.2.20:8188"
    comfy_timeout: int = 300

    root_path: Path = Path.home() / "img2ec" / "projects"

    cors_origins: list[str] = ["http://localhost:3000"]


def get_settings() -> Settings:
    return Settings()
