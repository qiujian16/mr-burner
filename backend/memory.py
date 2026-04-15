"""
Mempalace — file-based structured memory for layoff consultation sessions.

Layout on disk:
  data/
    _index.json          ← lightweight index of all sessions
    session_<id>.json    ← full session data (messages + extracted facts)
"""

import json
import os
from datetime import datetime
from typing import Optional, List


class ConsultationMemory:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._index_path = os.path.join(data_dir, "_index.json")
        if not os.path.exists(self._index_path):
            self._write_index({})

    # ── index helpers ────────────────────────────────────────────────────────

    def _read_index(self) -> dict:
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_index(self, index: dict):
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _sync_index(self, session: dict):
        index = self._read_index()
        sid = session["session_id"]
        index[sid] = {
            "session_id": sid,
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": len(session.get("messages", [])),
            "case_summary": session.get("case_summary"),
            "employee_name": session.get("employee_info", {}).get("name"),
            "has_analysis": bool(session.get("analysis")),
            "provider": session.get("provider", "claude"),
        }
        self._write_index(index)

    # ── session CRUD ─────────────────────────────────────────────────────────

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.data_dir, f"session_{session_id}.json")

    def create_session(self, session_id: str, provider: str = "claude") -> dict:
        now = datetime.now().isoformat()
        session = {
            "session_id": session_id,
            "provider": provider,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            # ── Mempalace rooms ──────────────────────────────────────
            "employee_info": {
                "name": None,
                "start_date": None,
                "years_of_service": None,
                "monthly_salary": None,
                "salary_12month_total": None,
                "unused_leave_days": None,
                "pending_bonus": None,
                "unvested_stocks_desc": None,
                "contract_type": None,
                "special_situation": None,
                "position": None,
            },
            "company_offer": {
                "offer_description": None,
                "n_base_salary": None,
                "compensation_months": None,
                "has_notice_pay": None,
                "total_amount": None,
                "conditions": None,
            },
            "case_summary": None,
            "analysis": None,
        }
        self._write_session(session)
        self._sync_index(session)
        return session

    def load_session(self, session_id: str) -> Optional[dict]:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_session(self, session: dict):
        session["updated_at"] = datetime.now().isoformat()
        with open(self._session_path(session["session_id"]), "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

    # ── message helpers ───────────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str):
        session = self.load_session(session_id)
        if not session:
            session = self.create_session(session_id)
        session["messages"].append(
            {"role": role, "content": content, "ts": datetime.now().isoformat()}
        )
        self._write_session(session)
        self._sync_index(session)

    # ── structured data updates ───────────────────────────────────────────────

    def update_employee_info(self, session_id: str, info: dict):
        session = self.load_session(session_id)
        if not session:
            return
        for k, v in info.items():
            if v is not None:
                session["employee_info"][k] = v
        self._write_session(session)
        self._sync_index(session)

    def update_company_offer(self, session_id: str, offer: dict):
        session = self.load_session(session_id)
        if not session:
            return
        for k, v in offer.items():
            if v is not None:
                session["company_offer"][k] = v
        self._write_session(session)
        self._sync_index(session)

    def update_case_summary(self, session_id: str, summary: str):
        session = self.load_session(session_id)
        if not session:
            return
        session["case_summary"] = summary
        self._write_session(session)
        self._sync_index(session)

    def update_analysis(self, session_id: str, analysis: str):
        session = self.load_session(session_id)
        if not session:
            return
        session["analysis"] = analysis
        self._write_session(session)
        self._sync_index(session)

    def delete_session(self, session_id: str) -> bool:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return False
        os.remove(path)
        index = self._read_index()
        index.pop(session_id, None)
        self._write_index(index)
        return True

    # ── listing ───────────────────────────────────────────────────────────────

    def list_sessions(self) -> List[dict]:
        index = self._read_index()
        sessions = list(index.values())
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
