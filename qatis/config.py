import os
import pathlib
from dataclasses import dataclass
from typing import Optional

from dotenv import dotenv_values


CONFIG_DIR = pathlib.Path.home() / ".qatis"
CONFIG_ENV = CONFIG_DIR / ".env"
PROMPTS_DIR = CONFIG_DIR / "prompts"


@dataclass
class Keys:
    openai_api_key: Optional[str] = None
    scraperapi_api_key: Optional[str] = None


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def load_keys() -> Keys:
    """Load keys with precedence: env vars > ~/.qatis/.env > project .env."""
    # Start from project .env
    project_env = {}
    if pathlib.Path(".env").exists():
        project_env = dotenv_values(".env")

    # Then user config
    user_env = {}
    if CONFIG_ENV.exists():
        user_env = dotenv_values(CONFIG_ENV)

    def pick(name: str) -> Optional[str]:
        return (
            os.getenv(name)
            or user_env.get(name)
            or project_env.get(name)
        )

    return Keys(
        openai_api_key=(pick("OPENAI_API_KEY") or None),
        scraperapi_api_key=(pick("SCRAPERAPI_API_KEY") or None),
    )


def save_keys(keys: Keys):
    ensure_dirs()
    # Merge with existing
    existing = {}
    if CONFIG_ENV.exists():
        existing = dotenv_values(CONFIG_ENV)
    existing = dict(existing)
    if keys.openai_api_key is not None:
        existing["OPENAI_API_KEY"] = keys.openai_api_key
    if keys.scraperapi_api_key is not None:
        existing["SCRAPERAPI_API_KEY"] = keys.scraperapi_api_key

    # Write
    lines = [f"{k}={v}" for k, v in existing.items() if v]
    CONFIG_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


