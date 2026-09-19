"""Rule-based natural language query understanding."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTORS = [
    "renewables", "mining", "railways", "powerline", "construction",
    "others", "dsp", "tender", "manufacturing", "energy", "aviation",
]

INTENTS = [
    "pipeline",
    "revenue",
    "sector",
    "operations",
    "owner",
    "leadership",
    "cross_board",
    "help",
    "clarify",
]


@dataclass
class ParsedQuery:
    intent: str
    sector: str | None = None
    quarter: bool = False
    owner: str | None = None
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    raw: str = ""
    keywords: list[str] = field(default_factory=list)


class QueryParser:
    def parse(self, text: str) -> ParsedQuery:
        raw = text.strip()
        lower = raw.lower()
        keywords = re.findall(r"[a-zA-Z]+", lower)

        sector = self._extract_sector(lower)
        quarter = any(w in lower for w in ["quarter", "q1", "q2", "q3", "q4", "this quarter"])
        owner = self._extract_owner(raw)

        if any(w in lower for w in ["help", "what can you", "how do i", "examples"]):
            return ParsedQuery(intent="help", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["leadership", "executive", "founder update", "board update", "brief"]):
            return ParsedQuery(intent="leadership", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["owner", "kam", "sales rep", "personnel"]):
            return ParsedQuery(intent="owner", sector=sector, quarter=quarter, owner=owner, raw=raw, keywords=keywords)

        if any(w in lower for w in ["revenue", "billed", "billing", "collected", "receivable", "invoice"]):
            return ParsedQuery(intent="revenue", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["work order", "execution", "delivery", "ongoing", "completed", "operations"]):
            return ParsedQuery(intent="operations", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["sector", "vertical", "industry", "segment", "performance by"]):
            return ParsedQuery(intent="sector", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["pipeline", "deals", "open deals", "won", "closure", "forecast", "looking"]):
            if sector and quarter:
                return ParsedQuery(intent="pipeline", sector=sector, quarter=True, raw=raw, keywords=keywords)
            if sector:
                return ParsedQuery(intent="pipeline", sector=sector, quarter=quarter, raw=raw, keywords=keywords)
            if quarter and not sector:
                if "energy" in lower:
                    return ParsedQuery(intent="pipeline", sector="Renewables", quarter=True, raw=raw, keywords=keywords)
                return ParsedQuery(
                    intent="clarify",
                    quarter=True,
                    needs_clarification=True,
                    clarification_prompt="Which sector should I filter for this quarter's pipeline?",
                    raw=raw,
                    keywords=keywords,
                )
            return ParsedQuery(intent="pipeline", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if any(w in lower for w in ["compare", "across", "both boards", "end to end"]):
            return ParsedQuery(intent="cross_board", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

        if len(lower.split()) < 3:
            return ParsedQuery(
                intent="clarify",
                needs_clarification=True,
                clarification_prompt="Could you share more detail? For example: pipeline for Mining this quarter, or revenue from work orders.",
                raw=raw,
                keywords=keywords,
            )

        return ParsedQuery(intent="cross_board", sector=sector, quarter=quarter, raw=raw, keywords=keywords)

    @staticmethod
    def _extract_sector(text: str) -> str | None:
        for s in SECTORS:
            if s in text:
                mapping = {
                    "energy": "Renewables",
                    "renewables": "Renewables",
                    "mining": "Mining",
                    "railways": "Railways",
                    "powerline": "Powerline",
                    "construction": "Construction",
                    "others": "Others",
                    "dsp": "DSP",
                    "tender": "Tender",
                    "manufacturing": "Manufacturing",
                    "aviation": "Aviation",
                }
                return mapping.get(s, s.title())
        return None

    @staticmethod
    def _extract_owner(text: str) -> str | None:
        match = re.search(r"OWNER_\d+", text, re.IGNORECASE)
        return match.group(0).upper() if match else None
