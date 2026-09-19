"""Leadership update brief generator."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.bi.analytics import BusinessAnalytics, _inr


class LeadershipBrief:
    """Prepare a concise executive snapshot for leadership updates."""

    def __init__(self, analytics: BusinessAnalytics):
        self.analytics = analytics

    def generate(self) -> dict:
        pipeline = self.analytics.pipeline_summary()
        revenue = self.analytics.revenue_operations()
        sectors = self.analytics.sector_performance()
        quality = self._quality_flags()

        top_sectors = sectors.nlargest(3, "pipeline_value") if not sectors.empty else pd.DataFrame()
        at_risk = self._at_risk_deals()

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "headline": self._headline(pipeline, revenue),
            "pipeline": pipeline,
            "revenue": revenue,
            "top_sectors": top_sectors,
            "at_risk_deals": at_risk,
            "quality_flags": quality,
            "markdown": self._to_markdown(pipeline, revenue, top_sectors, at_risk, quality),
        }

    def _headline(self, pipeline: dict, revenue: dict) -> str:
        open_val = pipeline.get("open_value") or 0
        billed = revenue.get("total_billed") or 0
        return (
            f"Open pipeline stands at {_inr(open_val)} across {pipeline.get('open_count', 0)} deals; "
            f"operations have billed {_inr(billed)} to date."
        )

    def _at_risk_deals(self, limit: int = 5) -> pd.DataFrame:
        df = self.analytics.deals
        open_deals = df[df["deal_status"] == "Open"].copy()
        open_deals["risk_score"] = 0
        open_deals.loc[open_deals["closure_probability"].isin(["Low", None]), "risk_score"] += 2
        open_deals.loc[open_deals["deal_value"].isna(), "risk_score"] += 1
        open_deals.loc[open_deals["tentative_close_date"].isna(), "risk_score"] += 1
        cols = ["deal_name", "sector", "deal_stage", "deal_value", "closure_probability", "tentative_close_date"]
        return open_deals.sort_values("risk_score", ascending=False).head(limit)[cols]

    def _quality_flags(self) -> list[str]:
        deals = self.analytics.deals
        wo = self.analytics.work_orders
        flags = []
        if deals["deal_value"].isna().sum() > len(deals) * 0.3:
            flags.append("Over 30% of deals lack value — pipeline totals are understated.")
        if wo["billed_ex_gst"].isna().sum() > len(wo) * 0.4:
            flags.append("Billing data is sparse on work orders — revenue view is partial.")
        stale = wo[wo["execution_status"] == "Ongoing"]
        if len(stale) > 0:
            flags.append(f"{len(stale)} work orders marked ongoing — validate delivery timelines.")
        return flags

    def _to_markdown(
        self,
        pipeline: dict,
        revenue: dict,
        top_sectors: pd.DataFrame,
        at_risk: pd.DataFrame,
        quality: list[str],
    ) -> str:
        lines = [
            "# Skylark Leadership Update",
            "",
            f"**Headline:** {self._headline(pipeline, revenue)}",
            "",
            "## Pipeline",
            self.analytics.format_pipeline_summary(pipeline),
            "",
            "## Operations & Revenue",
            self.analytics.format_revenue_summary(revenue),
            "",
            "## Top Sectors (Open Pipeline)",
        ]
        if not top_sectors.empty:
            for _, row in top_sectors.iterrows():
                lines.append(
                    f"- **{row['sector']}**: {_inr(row['pipeline_value'])} pipeline, "
                    f"{int(row['deals_open'])} open / {int(row['deals_won'])} won"
                )
        else:
            lines.append("- No sector data available")

        lines.extend(["", "## Deals to Watch"])
        if not at_risk.empty:
            for _, row in at_risk.iterrows():
                lines.append(
                    f"- {row['deal_name']} ({row['sector']}): {_inr(row['deal_value'])}, "
                    f"stage {row['deal_stage']}, prob {row['closure_probability'] or 'unknown'}"
                )
        else:
            lines.append("- No at-risk open deals identified")

        if quality:
            lines.extend(["", "## Data Quality Flags"])
            for flag in quality:
                lines.append(f"- {flag}")

        return "\n".join(lines)
