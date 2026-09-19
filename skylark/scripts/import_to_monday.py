"""
Optional helper: import Excel data into Monday.com boards.

Requires MONDAY_API_TOKEN and board IDs. Column titles should match
the cleaned field names you configure on your boards.

Usage:
  python scripts/import_to_monday.py --deals-board-id XXX --wo-board-id YYY
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import MONDAY_API_TOKEN, MONDAY_API_URL, DEALS_FILE, WORK_ORDERS_FILE
from src.data.cleaner import clean_deals, clean_work_orders


def create_item(board_id: str, item_name: str, column_values: dict) -> None:
    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
      create_item(board_id: $boardId, item_name: $itemName, column_values: $columnValues) {
        id
      }
    }
    """
    headers = {"Authorization": MONDAY_API_TOKEN, "Content-Type": "application/json"}
    variables = {
        "boardId": int(board_id),
        "itemName": item_name,
        "columnValues": column_values,
    }
    resp = requests.post(
        MONDAY_API_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deals-board-id")
    parser.add_argument("--wo-board-id")
    parser.add_argument("--limit", type=int, default=10, help="Items per board (demo limit)")
    args = parser.parse_args()

    if not MONDAY_API_TOKEN:
        raise SystemExit("Set MONDAY_API_TOKEN in .env")

    if args.deals_board_id:
        deals = clean_deals(pd.read_excel(DEALS_FILE)).head(args.limit)
        for _, row in deals.iterrows():
            create_item(args.deals_board_id, row["deal_name"] or "Untitled", {})
        print(f"Imported {len(deals)} deals")

    if args.wo_board_id:
        wo = clean_work_orders(pd.read_excel(WORK_ORDERS_FILE)).head(args.limit)
        for _, row in wo.iterrows():
            create_item(args.wo_board_id, row["deal_name"] or "Untitled", {})
        print(f"Imported {len(wo)} work orders")


if __name__ == "__main__":
    main()
