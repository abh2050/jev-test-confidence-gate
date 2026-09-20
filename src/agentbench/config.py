"""Environment loading.

The project `.env` may hold a bare API key on its own line, with no `NAME=`,
which is how the TypeSafe console hands it out. Both that shape and ordinary
`NAME=value` lines are accepted, so parsing is done here rather than pulling in
a dotenv dependency for two cases.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

_TYPESAFE_PREFIX = "apikey_"


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env(path: Path | None = None) -> None:
    """Populate os.environ from .env. Real environment variables win."""
    env_path = path or ENV_PATH
    if not env_path.exists():
        return

    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            name, _, value = line.partition("=")
            name, value = name.strip(), _unquote(value.strip())
            if name and value and name not in os.environ:
                os.environ[name] = value
        elif line.startswith(_TYPESAFE_PREFIX) and "TYPESAFE_API_KEY" not in os.environ:
            # A bare key line, pasted straight from the console.
            os.environ["TYPESAFE_API_KEY"] = line


def require(name: str, hint: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. {hint}")
    return value


def openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def typesafe_model() -> str:
    return os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
