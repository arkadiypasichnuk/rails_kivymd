"""Пути к ресурсам. Считаются от расположения проекта, а не от текущей папки."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
ASSETS = ROOT / "assets"
KV_DIR = PACKAGE_DIR / "kv"
DEFAULT_LEVELS = ROOT / "suns" / "build-in" / "Main.toml"


def asset(*parts: str) -> str:
    """Путь к файлу в assets/ (строкой — так удобнее Kivy)."""
    return str(ASSETS.joinpath(*parts))
