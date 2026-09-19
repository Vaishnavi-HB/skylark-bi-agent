import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")
MONDAY_DEALS_BOARD_ID = os.getenv("MONDAY_DEALS_BOARD_ID", "")
MONDAY_WORK_ORDERS_BOARD_ID = os.getenv("MONDAY_WORK_ORDERS_BOARD_ID", "")
DATA_SOURCE = os.getenv("DATA_SOURCE", "local").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MONDAY_API_URL = "https://api.monday.com/v2"

DEALS_FILE = DATA_DIR / "Deal funnel Data.xlsx"
WORK_ORDERS_FILE = DATA_DIR / "Work_Order_Tracker Data.xlsx"
