"""Unified data access layer."""

from __future__ import annotations

import pandas as pd

from src.config import DATA_SOURCE, MONDAY_API_TOKEN
from src.data.local_loader import load_deals_local, load_work_orders_local
from src.data.monday_client import MondayClient, MondayClientError


class DataRepository:
    def __init__(self, source: str | None = None):
        self.requested_source = (source or DATA_SOURCE).lower()
        self.effective_source = self.requested_source
        self.fallback_reason: str | None = None

    def _monday_configured(self) -> bool:
        return bool(MONDAY_API_TOKEN)

    def load_deals(self) -> pd.DataFrame:
        if self.effective_source == "monday":
            return MondayClient().load_deals()
        return load_deals_local()

    def load_work_orders(self) -> pd.DataFrame:
        if self.effective_source == "monday":
            return MondayClient().load_work_orders()
        return load_work_orders_local()

    def load_all(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.requested_source == "monday" and not self._monday_configured():
            self.effective_source = "local"
            self.fallback_reason = "MONDAY_API_TOKEN is not configured — using local Excel data."

        try:
            deals = self.load_deals()
            work_orders = self.load_work_orders()
            return deals, work_orders
        except MondayClientError as exc:
            self.effective_source = "local"
            self.fallback_reason = f"Monday.com unavailable ({exc}) — using local Excel data."
            return load_deals_local(), load_work_orders_local()

    def data_quality_summary(self, deals: pd.DataFrame, work_orders: pd.DataFrame) -> dict:
        return {
            "deals_total": len(deals),
            "deals_missing_value": int(deals["deal_value"].isna().sum()) if "deal_value" in deals else 0,
            "deals_open": int((deals["deal_status"] == "Open").sum()) if "deal_status" in deals else 0,
            "work_orders_total": len(work_orders),
            "wo_missing_billed": int(work_orders["billed_ex_gst"].isna().sum()) if "billed_ex_gst" in work_orders else 0,
            "wo_ongoing": int((work_orders["execution_status"] == "Ongoing").sum()) if "execution_status" in work_orders else 0,
        }
