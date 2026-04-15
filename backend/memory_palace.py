"""
MemPalace integration — semantic memory for layoff consultation sessions.

Palace layout on disk:
  palace/
    layoff_cases/          ← wing: one text file per session
      session_<id>.txt
    (ChromaDB data lives at palace_path root, managed by mempalace)
"""

import os
from pathlib import Path

# Rooms that capture different aspects of a consultation
ROOMS = [
    "economic_compensation",   # N / 2N calculations
    "negotiation",             # strategy and communication
    "stocks_equity",           # RSU / ESOP / options
    "leave_bonus",             # unused leave, bonuses
    "case_details",            # factual case summary
    "general",                 # catch-all
]

WING = "layoff_cases"


def _session_to_text(session: dict) -> str:
    """Convert session data into a searchable plain-text document."""
    lines = []

    if session.get("case_summary"):
        lines.append(f"案例摘要: {session['case_summary']}")

    emp = session.get("employee_info") or {}
    if emp.get("position"):
        lines.append(f"职位: {emp['position']}")
    if emp.get("years_of_service"):
        lines.append(f"工作年限: {emp['years_of_service']}年")
    if emp.get("monthly_salary"):
        lines.append(f"月薪基数: {emp['monthly_salary']}元")
    if emp.get("salary_12month_total"):
        lines.append(f"12个月工资总额: {emp['salary_12month_total']}元")
    if emp.get("unvested_stocks_desc"):
        lines.append(f"股权情况: {emp['unvested_stocks_desc']}")
    if emp.get("pending_bonus"):
        lines.append(f"待发奖金: {emp['pending_bonus']}元")
    if emp.get("unused_leave_days"):
        lines.append(f"未休年假: {emp['unused_leave_days']}天")
    if emp.get("special_situation"):
        lines.append(f"特殊情形: {emp['special_situation']}")

    offer = session.get("company_offer") or {}
    if offer.get("offer_description"):
        lines.append(f"公司方案: {offer['offer_description']}")
    if offer.get("compensation_months"):
        lines.append(f"赔偿月数: {offer['compensation_months']}个月")
    if offer.get("total_amount"):
        lines.append(f"方案总额: {offer['total_amount']}元")

    # Include key conversation exchanges (last 20 messages, truncated)
    for msg in session.get("messages", [])[-20:]:
        role = "员工" if msg["role"] == "user" else "顾问"
        content = msg["content"][:400]
        lines.append(f"{role}: {content}")

    if session.get("analysis"):
        lines.append(f"分析报告摘要: {session['analysis'][:600]}")

    return "\n".join(lines)


class MemPalaceStore:
    """
    Wrapper around the mempalace library for semantic memory.

    Falls back gracefully if mempalace / chromadb is unavailable.
    """

    def __init__(self, palace_path: str):
        self.palace_path = Path(palace_path).resolve()
        self._available = False

        try:
            from mempalace.palace import get_collection, get_closets_collection
            self._get_collection = get_collection
            self._get_closets_collection = get_closets_collection
            from mempalace.miner import process_file
            self._process_file = process_file
            from mempalace.searcher import search_memories
            self._search_memories = search_memories

            # Ensure palace wing directory exists
            wing_dir = self.palace_path / WING
            wing_dir.mkdir(parents=True, exist_ok=True)

            # Pre-open collections to validate palace is writable
            self._col = get_collection(str(self.palace_path))
            self._closets_col = get_closets_collection(str(self.palace_path))
            self._available = True
            print(f"[mempalace] palace ready at {self.palace_path}")

        except ImportError:
            print("[mempalace] library not installed — semantic memory disabled")
        except Exception as e:
            print(f"[mempalace] init error: {e} — semantic memory disabled")

    # ── Public API ────────────────────────────────────────────────────────────

    def mine_session(self, session_id: str, session: dict):
        """Write session data to the palace so future chats can find it."""
        if not self._available:
            return

        try:
            # Write session as plain text file inside the wing directory
            file_path = self.palace_path / WING / f"session_{session_id}.txt"
            text = _session_to_text(session)
            file_path.write_text(text, encoding="utf-8")

            # Mine the file into ChromaDB drawers + closets
            self._process_file(
                filepath=file_path,
                project_path=self.palace_path / WING,
                collection=self._col,
                wing=WING,
                rooms=ROOMS,
                agent="layoff_lawyer",
                dry_run=False,
                closets_col=self._closets_col,
            )
        except Exception as e:
            print(f"[mempalace] mine_session error: {e}")

    def search_context(self, query: str, n_results: int = 3) -> str:
        """
        Search past consultation sessions for relevant context.
        Returns a formatted string ready to prepend to the system prompt,
        or empty string if nothing relevant is found.
        """
        if not self._available:
            return ""

        try:
            results = self._search_memories(
                query=query,
                palace_path=str(self.palace_path),
                wing=WING,
                n_results=n_results,
                max_distance=0.85,  # cosine: 0=identical, 2=opposite; 0.85 keeps relevant
            )

            hits = results.get("results", []) if isinstance(results, dict) else []
            if not hits:
                return ""

            lines = ["【参考历史案例（语义匹配）】"]
            for hit in hits:
                text = hit.get("text", "").strip()
                if text:
                    lines.append(f"- {text[:300]}")

            return "\n".join(lines)

        except Exception as e:
            print(f"[mempalace] search_context error: {e}")
            return ""
