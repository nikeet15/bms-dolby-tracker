"""Background loop that monitors configured dates and alerts on openings."""

import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class Tracker:
    def __init__(self, store, notifier, scraper, interval_seconds: int) -> None:
        self.store = store
        self.notifier = notifier
        self.scraper = scraper
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._notified_once = {}
        self._last_sent_at = {}

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        """Wake the loop immediately if it is sleeping between checks."""
        logger.info("Config changed; running a check immediately.")
        self._wake.set()

    def on_config_changed(self, chat_id) -> None:
        """Reset per-chat alert state so new preferences can fire, then check now."""
        cid = str(chat_id)
        self._notified_once = {
            key: True for key in self._notified_once if key[0] != cid
        }
        self._last_sent_at = {
            key: ts for key, ts in self._last_sent_at.items() if key[0] != cid
        }
        self.wake()

    def run(self) -> None:
        logger.info("Tracker started (checking every %ss).", self.interval_seconds)
        while not self._stop.is_set():
            logger.debug("Tracker cycle beginning.")
            try:
                self.check_once()
            except Exception:
                logger.exception("Unexpected tracker error.")
            self._wake.wait(self.interval_seconds)
            self._wake.clear()

    def check_once(self) -> None:
        chats = self.store.chats_with_dates()
        if not chats:
            logger.info("No dates configured; tracker idle.")
            return
        logger.info("Running check for %d chat(s)...", len(chats))
        for chat_id, dates in chats.items():
            timings = self.store.timings(chat_id)
            mode = self.store.notify_mode(chat_id)
            interval_minutes = self.store.notify_interval_minutes(chat_id)
            logger.info(
                "Chat %s dates=%s timings=%s notify=%s%s",
                chat_id,
                ", ".join(dates) or "none",
                ", ".join(timings) or "any",
                mode,
                f" (every {interval_minutes}m)" if interval_minutes else "",
            )
            for iso in dates:
                day = iso.replace("-", "")
                try:
                    times = self.scraper.fetch_showtimes(day)
                except Exception as exc:
                    logger.error("Scrape failed for %s: %s", iso, exc)
                    continue

                key = (chat_id, iso)
                if not times:
                    self._notified_once.pop(key, None)
                    logger.info("Date %s: no open bookings yet.", iso)
                    continue

                matched = times if not timings else [t for t in times if t in timings]
                if not matched:
                    logger.info(
                        "Date %s open but none of preferred timings %s available.",
                        iso,
                        ", ".join(timings),
                    )
                    continue

                if self._should_alert(key, mode, interval_minutes):
                    pretty = datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
                    self.notifier.send(
                        chat_id,
                        "\U0001f39f\ufe0f BOOKING OPEN! \U0001f39f\ufe0f\n\n"
                        f"Date: {pretty}\n"
                        f"Timings: {', '.join(matched)}\n"
                        f"URL: {self.scraper.url_for(day)}",
                    )
                    self._last_sent_at[key] = time.time()
                    logger.info("Alerted chat %s for %s", chat_id, iso)

    def _should_alert(self, key, mode: str, interval_minutes) -> bool:
        """Decide whether to send an alert for a (chat, date) in this cycle."""
        if mode == "every":
            if not interval_minutes:
                return True
            last = self._last_sent_at.get(key, 0)
            return time.time() - last >= interval_minutes * 60

        # "once" mode: alert only the first time this date opens
        if key not in self._notified_once:
            self._notified_once[key] = True
            return True
        return False


__all__ = ["Tracker"]
