from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"
DOTENV_PATH = PROJECT_ROOT / ".env"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
TMP_DIR = RUNTIME_DIR / "tmp"
ASSETS_DIR = PROJECT_ROOT / "assets"
