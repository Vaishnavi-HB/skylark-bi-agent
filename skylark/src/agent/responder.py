"""Conversational BI agent orchestrator."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.agent.query_parser import ParsedQuery, QueryParser
from src.bi.analytics import BusinessAnalytics, _inr
from src.bi.leadership import LeadershipBrief
from src.config import OPENAI_API_KEY, OPENAI_MODEL


class BIAgent:
    def __init__(self, deals: pd.DataFrame, work_orders: pd.DataFrame):
        self.deals = deals
        self.work_orders = work_orders
        self.analytics = BusinessAnalytics(deals, work_orders)
        self.parser = QueryParser()

    def ask(self, question: str) -> dict[str, Any]:
        parsed = self.parser.parse(question)
        if parsed.needs_clarification:
            return {
                "answer": parsed.clarification_prompt,
                "intent": parsed.intent,
                "data": None,
                "charts": None,
            }

        handler = {
            "help": self._help,
            "pipeline": self._pipeline,
            "revenue": self._revenue,
            "sector": self._sector,
            "operations": self._operations,
            "owner": self._owner,
            "leadership": self._leadership,
            "cross_board": self._cross_board,
            "clarify": self._clarify,
        }.get(parsed.intent, self._cross_board)

        result = handler(parsed)
        result["answer"] = self._maybe_enhance_with_llm(question, result["answer"], parsed)
        return result

    def _help(self, _: ParsedQuery) -> dict[str, Any]:
        text = """I can answer founder-level questions across **Deals** and **Work Orders** boards.

**Example questions:**
- How's our pipeline looking for Mining this quarter?
- What's our revenue and billing status?
- Show sector performance across sales and delivery
- Which deals are at risk?
- Prepare a leadership update
- How is OWNER_001 performing?

I handle missing data gracefully and will flag data quality caveats."""
        return {"answer": text, "intent": "help", "data": None, "charts": None}

    def _pipeline(self, q: ParsedQuery) -> dict[str, Any]:
        summary = self.analytics.pipeline_summary(sector=q.sector, quarter=q.quarter)
        answer = self.analytics.format_pipeline_summary(summary)
        if q.quarter:
            answer = "**This quarter filter applied** (by tentative/close date)\n\n" + answer
        chart = summary["by_sector"] if q.sector is None else summary["by_stage"]
        return {"answer": answer, "intent": "pipeline", "data": summary, "charts": {"pipeline": chart}}

    def _revenue(self, q: ParsedQuery) -> dict[str, Any]:
        rev = self.analytics.revenue_operations()
        answer = self.analytics.format_revenue_summary(rev)
        if q.sector:
            wo = self.work_orders[self.work_orders["sector"].str.lower() == q.sector.lower()]
            sector_billed = wo["billed_ex_gst"].sum(min_count=1)
            answer += f"\n\n**{q.sector} billed:** {_inr(sector_billed)}"
        return {"answer": answer, "intent": "revenue", "data": rev, "charts": {"execution": rev["by_execution_status"]}}

    def _sector(self, _: ParsedQuery) -> dict[str, Any]:
        df = self.analytics.sector_performance()
        lines = ["**Sector performance (Deals + Work Orders)**"]
        for _, row in df.head(8).iterrows():
            lines.append(
                f"- **{row['sector']}**: pipeline {_inr(row['pipeline_value'])}, "
                f"won {_inr(row['won_value'])}, {int(row['work_orders'])} WOs, "
                f"win rate {row['win_rate_pct']}%"
            )
        return {"answer": "\n".join(lines), "intent": "sector", "data": df, "charts": {"sectors": df}}

    def _operations(self, q: ParsedQuery) -> dict[str, Any]:
        wo = self.work_orders
        if q.sector:
            wo = wo[wo["sector"].str.lower() == q.sector.lower()]
        by_status = (
            wo.groupby("execution_status")
            .agg(count=("deal_name", "count"), value=("contract_value_ex_gst", "sum"))
            .reset_index()
            .sort_values("count", ascending=False)
        )
        lines = [f"**Work order operations{' — ' + q.sector if q.sector else ''}**"]
        for _, row in by_status.iterrows():
            lines.append(f"- {row['execution_status']}: {int(row['count'])} WOs ({_inr(row['value'])})")
        ongoing = len(wo[wo["execution_status"] == "Ongoing"])
        not_started = len(wo[wo["execution_status"] == "Not Started"])
        lines.append(f"\n**Active delivery:** {ongoing} ongoing, {not_started} not started")
        return {"answer": "\n".join(lines), "intent": "operations", "data": by_status, "charts": {"ops": by_status}}

    def _owner(self, q: ParsedQuery) -> dict[str, Any]:
        df = self.analytics.owner_performance()
        if q.owner:
            df = df[df["owner_code"] == q.owner]
        lines = ["**Owner / KAM performance**"]
        for _, row in df.head(10).iterrows():
            lines.append(
                f"- {row['owner_code']}: {int(row['deals'])} deals, "
                f"{int(row['open'])} open, {int(row['won'])} won, pipeline {_inr(row['pipeline'])}"
            )
        return {"answer": "\n".join(lines), "intent": "owner", "data": df, "charts": None}

    def _leadership(self, _: ParsedQuery) -> dict[str, Any]:
        brief = LeadershipBrief(self.analytics).generate()
        return {
            "answer": brief["markdown"],
            "intent": "leadership",
            "data": brief,
            "charts": None,
        }

    def _cross_board(self, q: ParsedQuery) -> dict[str, Any]:
        insight = self.analytics.cross_board_insights(sector=q.sector)
        lines = [
            f"**Cross-board view — {insight['sector']}**",
            f"- Open pipeline: {_inr(insight['open_pipeline'])}",
            f"- Active work orders: {insight['active_work_orders']} ({_inr(insight['active_delivery_value'])})",
            f"- Won deals: {insight['won_deals']}",
            f"- Completed projects: {insight['completed_projects']}",
        ]
        rev = self.analytics.revenue_operations()
        lines.append(f"- Total billed (all sectors): {_inr(rev['total_billed'])}")
        return {"answer": "\n".join(lines), "intent": "cross_board", "data": insight, "charts": None}

    def _clarify(self, q: ParsedQuery) -> dict[str, Any]:
        return {
            "answer": q.clarification_prompt or "Could you rephrase your question?",
            "intent": "clarify",
            "data": None,
            "charts": None,
        }

    def _maybe_enhance_with_llm(self, question: str, answer: str, parsed: ParsedQuery) -> str:
        if not OPENAI_API_KEY or parsed.intent in {"help", "leadership"}:
            return answer
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise BI assistant for Skylark Drones founders. "
                            "Rewrite the analytics answer with clear insights and 1-2 actionable recommendations. "
                            "Keep numbers exactly as given. Mention data caveats if present."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nAnalytics answer:\n{answer}",
                    },
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content or answer
        except Exception:
            return answer
