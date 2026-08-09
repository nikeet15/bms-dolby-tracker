"""Thread-safe, JSON-backed persistence of per-chat user preferences."""

import json
import threading
from pathlib import Path


class Store:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._chats: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with self._lock:
                self._chats = json.loads(self._path.read_text())

    def _persist(self) -> None:
        self._path.write_text(json.dumps(self._chats, indent=2))

    def _ensure(self, chat_id) -> str:
        cid = str(chat_id)
        self._chats.setdefault(
            cid,
            {
                "dates": [],
                "timings": [],
                "pending_selection": None,
                "notify_mode": "once",
                "notify_interval_minutes": None,
            },
        )
        return cid

    def set_dates(self, chat_id, dates) -> None:
        with self._lock:
            cid = self._ensure(chat_id)
            self._chats[cid]["dates"] = list(dates)
            self._persist()

    def dates(self, chat_id) -> list:
        with self._lock:
            return list(self._chats.get(str(chat_id), {}).get("dates", []))

    def set_timings(self, chat_id, timings) -> None:
        with self._lock:
            cid = self._ensure(chat_id)
            self._chats[cid]["timings"] = list(timings)
            self._persist()

    def timings(self, chat_id) -> list:
        with self._lock:
            return list(self._chats.get(str(chat_id), {}).get("timings", []))

    def set_pending_selection(self, chat_id, items) -> None:
        with self._lock:
            cid = self._ensure(chat_id)
            self._chats[cid]["pending_selection"] = items
            self._persist()

    def pending_selection(self, chat_id):
        with self._lock:
            return self._chats.get(str(chat_id), {}).get("pending_selection")

    def set_notify(self, chat_id, mode: str, interval_minutes=None) -> None:
        with self._lock:
            cid = self._ensure(chat_id)
            self._chats[cid]["notify_mode"] = mode
            self._chats[cid]["notify_interval_minutes"] = interval_minutes
            self._persist()

    def notify_mode(self, chat_id) -> str:
        with self._lock:
            return self._chats.get(str(chat_id), {}).get("notify_mode", "once")

    def notify_interval_minutes(self, chat_id):
        with self._lock:
            return self._chats.get(str(chat_id), {}).get("notify_interval_minutes")

    def clear(self, chat_id) -> None:
        with self._lock:
            cid = self._ensure(chat_id)
            self._chats[cid] = {
                "dates": [],
                "timings": [],
                "pending_selection": None,
                "notify_mode": "once",
                "notify_interval_minutes": None,
            }
            self._persist()

    def chats_with_dates(self) -> dict:
        with self._lock:
            return {
                cid: list(c.get("dates", []))
                for cid, c in self._chats.items()
                if c.get("dates")
            }
