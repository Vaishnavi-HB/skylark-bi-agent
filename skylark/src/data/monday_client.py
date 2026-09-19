"""Monday.com GraphQL API client (read-only)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from src.config import (
    MONDAY_API_TOKEN,
    MONDAY_API_URL,
    MONDAY_DEALS_BOARD_ID,
    MONDAY_WORK_ORDERS_BOARD_ID,
)
from src.data.cleaner import clean_deals, clean_work_orders


class MondayClientError(Exception):
    pass


class MondayClient:
    """Fetch board items from Monday.com and normalize to DataFrames."""

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or MONDAY_API_TOKEN
        if not self.api_token:
            raise MondayClientError("MONDAY_API_TOKEN is not configured")

    def _query(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2024-10",
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(MONDAY_API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise MondayClientError(f"Monday.com API request failed: {exc}") from exc

        data = response.json()
        if "errors" in data:
            raise MondayClientError(str(data["errors"]))
        return data["data"]

    def fetch_board_items(self, board_id: str) -> list[dict[str, Any]]:
        query = """
        query ($boardId: [ID!], $cursor: String) {
          boards(ids: $boardId) {
            columns { id title type }
            items_page(limit: 500, cursor: $cursor) {
              cursor
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                  type
                }
              }
            }
          }
        }
        """
        all_items: list[dict[str, Any]] = []
        cursor = None
        columns: list[dict[str, str]] = []

        while True:
            variables = {"boardId": [int(board_id)], "cursor": cursor}
            data = self._query(query, variables)
            boards = data.get("boards") or []
            if not boards:
                break

            board = boards[0]
            if not columns:
                columns = board.get("columns") or []

            page = board.get("items_page") or {}
            items = page.get("items") or []
            all_items.extend(items)
            cursor = page.get("cursor")
            if not cursor or not items:
                break

        return self._items_to_rows(all_items, columns)

    @staticmethod
    def _items_to_rows(items: list[dict], columns: list[dict]) -> list[dict[str, Any]]:
        col_map = {c["id"]: c["title"] for c in columns}
        rows = []
        for item in items:
            row = {"Deal Name": item.get("name")}
            for cv in item.get("column_values") or []:
                title = col_map.get(cv["id"], cv["id"])
                row[title] = cv.get("text") or ""
            rows.append(row)
        return rows

    def load_deals(self) -> pd.DataFrame:
        if not MONDAY_DEALS_BOARD_ID:
            raise MondayClientError("MONDAY_DEALS_BOARD_ID is not configured")
        rows = self.fetch_board_items(MONDAY_DEALS_BOARD_ID)
        return clean_deals(pd.DataFrame(rows))

    def load_work_orders(self) -> pd.DataFrame:
        if not MONDAY_WORK_ORDERS_BOARD_ID:
            raise MondayClientError("MONDAY_WORK_ORDERS_BOARD_ID is not configured")
        rows = self.fetch_board_items(MONDAY_WORK_ORDERS_BOARD_ID)
        return clean_work_orders(pd.DataFrame(rows))
