"""Load deals and work orders from local Excel files (dev / fallback)."""

from __future__ import annotations

import pandas as pd

from src.config import DEALS_FILE, WORK_ORDERS_FILE
from src.data.cleaner import clean_deals, clean_work_orders


def load_deals_local() -> pd.DataFrame:
    if not DEALS_FILE.exists():
        raise FileNotFoundError(f"Deals file not found: {DEALS_FILE}")
    raw = pd.read_excel(DEALS_FILE)
    return clean_deals(raw)


def load_work_orders_local() -> pd.DataFrame:
    if not WORK_ORDERS_FILE.exists():
        raise FileNotFoundError(f"Work orders file not found: {WORK_ORDERS_FILE}")
    raw = pd.read_excel(WORK_ORDERS_FILE)
    return clean_work_orders(raw)
