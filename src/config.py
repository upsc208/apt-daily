import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = DATA_DIR / "apt_trade.db"
    LAWD_CODES_PATH = DATA_DIR / "lawd_codes.json"
    
    # Public Data Portal API Config (Standard Endpoint)
    API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
    API_BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    API_DEV_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# Ensure DATA_DIR exists
Config.DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_lawd_codes() -> list[dict]:
    """Load nationwide sigungu lawd codes mapping."""
    if not Config.LAWD_CODES_PATH.exists():
        return []
    with open(Config.LAWD_CODES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
