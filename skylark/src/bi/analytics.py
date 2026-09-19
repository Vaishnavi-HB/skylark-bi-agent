"""Business intelligence calculations across deals and work orders."""

from __future__ import annotations

from datetime import datetime

import pandas as pd


def _inr(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if abs(value) >= 1e7:
        return f"₹{value / 1e7:.2f} Cr"
    if abs(value) >= 1e5:
        return f"₹{value / 1e5:.2f} L"
    return f"₹{value:,.0f}"


def _current_quarter_bounds(ref: datetime | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    ref = ref or datetime.now()
    quarter = (ref.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    start = pd.Timestamp(year=ref.year, month=start_month, day=1)
    if quarter == 4:
        end = pd.Timestamp(year=ref.year + 1, month=1, day=1) - pd.Timedelta(days=1)
    else:
        end = pd.Timestamp(year=ref.year, month=start_month + 3, day=1) - pd.Timedelta(days=1)
    return start, end


class BusinessAnalytics:
    def __init__(self, deals: pd.DataFrame, work_orders: pd.DataFrame):
        self.deals = deals
        self.work_orders = work_orders

    def pipeline_summary(self, sector: str | None = None, quarter: bool = False) -> dict:
        df = self.deals.copy()
        if sector:
            df = df[df["sector"].str.lower() == sector.lower()]

        if quarter:
            start, end = _current_quarter_bounds()
            mask = (
                (df["tentative_close_date"] >= start) & (df["tentative_close_date"] <= end)
            ) | (
                (df["close_date"] >= start) & (df["close_date"] <= end)
            )
            df = df[mask | df["deal_status"].isin(["Open", "Won"])]

        open_deals = df[df["deal_status"] == "Open"]
        won_deals = df[df["deal_status"] == "Won"]
        dead_deals = df[df["deal_status"] == "Dead"]

        open_value = open_deals["deal_value"].sum(min_count=1)
        won_value = won_deals["deal_value"].sum(min_count=1)
        weighted = open_deals.apply(self._weighted_value, axis=1).sum(min_count=1)

        by_stage = (
            open_deals.groupby("deal_stage")["deal_value"]
            .agg(["count", "sum"])
            .sort_values("sum", ascending=False)
            .reset_index()
        )

        by_sector = (
            open_deals.groupby("sector")["deal_value"]
            .agg(["count", "sum"])
            .sort_values("sum", ascending=False)
            .reset_index()
        )

        return {
            "scope": sector or "All sectors",
            "quarter_filter": quarter,
            "open_count": len(open_deals),
            "open_value": open_value,
            "won_count": len(won_deals),
            "won_value": won_value,
            "dead_count": len(dead_deals),
            "weighted_pipeline": weighted,
            "by_stage": by_stage,
            "by_sector": by_sector,
            "data_caveats": self._pipeline_caveats(df),
        }

    @staticmethod
    def _weighted_value(row: pd.Series) -> float | None:
        value = row.get("deal_value")
        if pd.isna(value):
            return None
        prob = row.get("closure_probability")
        weights = {"High": 0.7, "Med": 0.4, "Medium": 0.4, "Low": 0.15}
        weight = weights.get(prob, 0.25)
        return float(value) * weight

    def _pipeline_caveats(self, df: pd.DataFrame) -> list[str]:
        caveats = []
        missing_val = df["deal_value"].isna().sum()
        if missing_val:
            caveats.append(f"{missing_val} deals missing deal value (excluded from value totals where applicable)")
        missing_prob = df[df["deal_status"] == "Open"]["closure_probability"].isna().sum()
        if missing_prob:
            caveats.append(f"{missing_prob} open deals missing closure probability (assumed 25% weight)")
        return caveats

    def sector_performance(self) -> pd.DataFrame:
        deals = self.deals.copy()
        wo = self.work_orders.copy()

        deal_stats = (
            deals.groupby("sector")
            .agg(
                deals_total=("deal_name", "count"),
                deals_won=("deal_status", lambda s: (s == "Won").sum()),
                deals_open=("deal_status", lambda s: (s == "Open").sum()),
                pipeline_value=("deal_value", lambda s: s[deals.loc[s.index, "deal_status"] == "Open"].sum()),
                won_value=("deal_value", lambda s: s[deals.loc[s.index, "deal_status"] == "Won"].sum()),
            )
            .reset_index()
        )

        wo_stats = (
            wo.groupby("sector")
            .agg(
                work_orders=("deal_name", "count"),
                contract_value=("contract_value_ex_gst", "sum"),
                billed=("billed_ex_gst", "sum"),
                receivable=("receivable", "sum"),
                ongoing=("execution_status", lambda s: (s == "Ongoing").sum()),
            )
            .reset_index()
        )

        merged = deal_stats.merge(wo_stats, on="sector", how="outer").fillna(0)
        merged["win_rate_pct"] = (
            merged["deals_won"] / merged["deals_total"].replace(0, pd.NA) * 100
        ).round(1)
        return merged.sort_values("pipeline_value", ascending=False)

    def revenue_operations(self) -> dict:
        wo = self.work_orders
        total_contract = wo["contract_value_ex_gst"].sum(min_count=1)
        total_billed = wo["billed_ex_gst"].sum(min_count=1)
        total_collected = wo["collected"].sum(min_count=1)
        total_receivable = wo["receivable"].sum(min_count=1)

        by_status = (
            wo.groupby("execution_status")
            .agg(count=("deal_name", "count"), contract=("contract_value_ex_gst", "sum"))
            .reset_index()
            .sort_values("count", ascending=False)
        )

        billing_gaps = wo[
            (wo["billed_ex_gst"].fillna(0) == 0)
            & (wo["execution_status"].isin(["Completed", "Ongoing", "Executed until current month"]))
        ]

        return {
            "total_contract": total_contract,
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_receivable": total_receivable,
            "billing_rate_pct": (total_billed / total_contract * 100) if total_contract else None,
            "by_execution_status": by_status,
            "unbilled_active_count": len(billing_gaps),
            "unbilled_active_value": billing_gaps["contract_value_ex_gst"].sum(min_count=1),
        }

    def owner_performance(self) -> pd.DataFrame:
        deals = (
            self.deals.groupby("owner_code")
            .agg(
                deals=("deal_name", "count"),
                open=("deal_status", lambda s: (s == "Open").sum()),
                won=("deal_status", lambda s: (s == "Won").sum()),
                pipeline=("deal_value", lambda s: s[self.deals.loc[s.index, "deal_status"] == "Open"].sum()),
            )
            .reset_index()
            .sort_values("pipeline", ascending=False)
        )
        return deals

    def cross_board_insights(self, sector: str | None = None) -> dict:
        sector_filter = sector.lower() if sector else None
        deals = self.deals if not sector_filter else self.deals[self.deals["sector"].str.lower() == sector_filter]
        wo = self.work_orders if not sector_filter else self.work_orders[self.work_orders["sector"].str.lower() == sector_filter]

        open_pipeline = deals[deals["deal_status"] == "Open"]["deal_value"].sum(min_count=1)
        active_delivery = wo[wo["execution_status"].isin(["Ongoing", "Not Started", "Executed until current month"])]
        delivery_value = active_delivery["contract_value_ex_gst"].sum(min_count=1)

        return {
            "sector": sector or "All",
            "open_pipeline": open_pipeline,
            "active_work_orders": len(active_delivery),
            "active_delivery_value": delivery_value,
            "won_deals": len(deals[deals["deal_status"] == "Won"]),
            "completed_projects": len(wo[wo["execution_status"] == "Completed"]),
        }

    def format_pipeline_summary(self, summary: dict) -> str:
        lines = [
            f"**Pipeline — {summary['scope']}**",
            f"- Open deals: {summary['open_count']} ({_inr(summary['open_value'])})",
            f"- Won deals: {summary['won_count']} ({_inr(summary['won_value'])})",
            f"- Weighted pipeline: {_inr(summary['weighted_pipeline'])}",
            f"- Dead/Lost: {summary['dead_count']}",
        ]
        if summary["by_sector"] is not None and not summary["by_sector"].empty:
            top = summary["by_sector"].head(3)
            lines.append("\n**Top open pipeline by sector:**")
            for _, row in top.iterrows():
                lines.append(f"- {row['sector']}: {int(row['count'])} deals, {_inr(row['sum'])}")
        if summary["data_caveats"]:
            lines.append("\n**Data caveats:**")
            for c in summary["data_caveats"]:
                lines.append(f"- {c}")
        return "\n".join(lines)

    def format_revenue_summary(self, rev: dict) -> str:
        lines = [
            "**Operations & Revenue**",
            f"- Total contract value: {_inr(rev['total_contract'])}",
            f"- Total billed: {_inr(rev['total_billed'])}",
            f"- Collected: {_inr(rev['total_collected'])}",
            f"- Receivable: {_inr(rev['total_receivable'])}",
        ]
        if rev["billing_rate_pct"] is not None:
            lines.append(f"- Billing rate: {rev['billing_rate_pct']:.1f}%")
        lines.append(f"- Active but unbilled WOs: {rev['unbilled_active_count']} ({_inr(rev['unbilled_active_value'])})")
        return "\n".join(lines)
