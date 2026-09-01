from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _secret_configured(*names: str, min_len: int = 12) -> bool:
    for name in names:
        value = _env(name)
        if value and len(value) >= min_len:
            return True
    return False


ROOT_DIR = ROOT
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = Path(_env("DATABASE_PATH", str(DATA_DIR / "finint.db")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT / DATABASE_PATH
CHROMA_PATH = Path(_env("CHROMA_PATH", str(DATA_DIR / "chroma")))
if not CHROMA_PATH.is_absolute():
    CHROMA_PATH = ROOT / CHROMA_PATH

HTTP_TIMEOUT = float(_env("HTTP_TIMEOUT_SECONDS", "20"))

MARKET_KEY_SET = _secret_configured("MARKET_API_KEY", "FINNHUB_API_KEY", "ALPHA_VANTAGE_API_KEY")
NEWS_KEY_SET = _secret_configured("NEWS_API_KEY")
LLM_KEY_SET = _secret_configured("LLM_API_KEY", "OPENAI_API_KEY", min_len=20)
SEC_KEY_SET = _secret_configured("SEC_API_KEY")

OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")

USER_AGENT = "FININT/1.0 (research; local investor terminal)"
TZ_NAME = "Asia/Kolkata"
