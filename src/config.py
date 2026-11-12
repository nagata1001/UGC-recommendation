from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
CACHE_DIR = ROOT / ".cache"
INDEX_DIR = ROOT / "indexes"
DATA_DIR = ROOT / "data"

MODEL_ID = "OFA-Sys/chinese-clip-vit-base-patch16"
MODEL_DIR = MODELS_DIR / "chinese-clip-vit-base-patch16"


def configure_local_cache() -> None:
    """Keep every third-party cache inside the project directory."""
    project_user_home = CACHE_DIR / "userhome"
    project_user_home.mkdir(parents=True, exist_ok=True)
    # Paddle 3.2 derives one legacy cache from expanduser("~") and ignores
    # PADDLE_HOME. Override USERPROFILE only for this Python process so the
    # cache remains inside the project instead of C:\\Users\\... .
    os.environ["USERPROFILE"] = str(project_user_home)
    paths = {
        "HF_HOME": CACHE_DIR / "huggingface",
        "HF_HUB_CACHE": CACHE_DIR / "huggingface" / "hub",
        "PADDLE_HOME": CACHE_DIR / "paddle",
        "PADDLEX_HOME": CACHE_DIR / "paddlex",
        "PADDLE_PDX_CACHE_HOME": CACHE_DIR / "paddlex",
        "XDG_CACHE_HOME": CACHE_DIR,
    }
    for key, value in paths.items():
        os.environ.setdefault(key, str(value))
        value.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


configure_local_cache()

