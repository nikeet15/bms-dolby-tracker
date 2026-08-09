"""Telegram bot: handles user commands and replies over long-polling."""

import logging
import re
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

DATE_FORMATS = ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y")

HELP_TEXT = (
    "Commands:\n"
    "/setdate 15-08-2026, 16-08-2026 - dates to watch\n"
    "/settime - tap to pick your preferred showtimes\n"
    "/notify once|every 5 - how often to alert you\n"
    "/status - your current settings\n"
    "/clear - show all commands again\n"
    "/reset - remove all dates and timings"
)


def parse_dates(text: str) -> list:
    """Parse a comma/space-separated list of dates into date objects."""
    dates = []
    for token in re.split(r"[,;\s]+", text.strip()):
        if not token:
            continue
        for fmt in DATE_FORMATS:
            try:
                dates.append(datetime.strptime(token, fmt).date())
                break
            except ValueError:
                continue
    return dates


def parse_selection(text: str, max_index: int) -> list:
    """Parse '1,3,5' style replies into a list of 1-based indices."""
    indices = []
    for token in re.split(r"[,;\s]+", text.strip()):
        if token.isdigit():
            n = int(token)
            if 1 <= n <= max_index:
                indices.append(n)
    return sorted(set(indices))


def _short_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")


class TelegramBot:
    def __init__(
        self, token: str, store, scraper, notifier, on_change=None, interval_seconds=900
    ) -> None:
        self.api = f"https://api.telegram.org/bot{token}"
        self.store = store
        self.scraper = scraper
        self.notifier = notifier
        self.on_change = on_change
        self.interval_seconds = interval_seconds
        self._offset = 0
        self._running = True

    def _interval_text(self) -> str:
        minutes = self.interval_seconds // 60
        return f"every {minutes} minute{'s' if minutes != 1 else ''}"

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        logger.info("Bot started (long-polling Telegram).")
        while self._running:
            try:
                for update in self._get_updates():
                    self._offset = update["update_id"] + 1
                    if update.get("callback_query"):
                        logger.debug(
                            "Callback query received: %r",
                            update["callback_query"].get("data"),
                        )
                        self._handle_callback_query(update["callback_query"])
                    elif update.get("message"):
                        self._handle_message(update["message"])
            except requests.RequestException as exc:
                logger.error(
                    "Telegram polling failed (status=%s): %s",
                    getattr(exc.response, "status_code", None),
                    exc.__class__.__name__,
                )
                time.sleep(5)

    def _get_updates(self) -> list:
        response = requests.get(
            f"{self.api}/getUpdates",
            params={"timeout": 25, "offset": self._offset},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("result", [])

    def _post(self, method: str, **params):
        """POST a Telegram API method, logging failures instead of raising."""
        try:
            response = requests.post(
                f"{self.api}/{method}", json=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error(
                "Telegram %s failed (status=%s): %s",
                method,
                getattr(exc.response, "status_code", None),
                exc.__class__.__name__,
            )
            return None

    def _reply(self, chat_id, text: str) -> None:
        self.notifier.send(chat_id, text)

    def _notify_change(self, chat_id) -> None:
        if self.on_change:
            try:
                self.on_change(chat_id)
            except Exception:
                logger.exception("Config-change callback failed.")

    # ---------------------------------------------------------------- commands

    def _handle_message(self, message) -> None:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            return

        command, _, arg = text.partition(" ")
        command = command.lower()
        logger.info("Message from chat %s: %r", chat_id, text)

        if command in ("/start", "/help"):
            logger.info("Chat %s requested help.", chat_id)
            self._reply(
                chat_id,
                "Welcome! I watch Allu Cinemas (Kokapet) on BookMyShow.\n\n"
                f"I check the venue {self._interval_text()}, and alert you based "
                "on your /notify setting.\n\n"
                + HELP_TEXT,
            )
        elif command == "/setdate":
            logger.info("Chat %s ran /setdate with args: %r", chat_id, arg)
            self._set_date(chat_id, arg)
        elif command == "/settime":
            logger.info("Chat %s ran /settime.", chat_id)
            self._set_timings(chat_id)
        elif command == "/notify":
            logger.info("Chat %s ran /notify with args: %r", chat_id, arg)
            self._set_notify(chat_id, arg)
        elif command == "/status":
            logger.info("Chat %s requested status.", chat_id)
            self._status(chat_id)
        elif command == "/clear":
            logger.info("Chat %s cleared pending selection.", chat_id)
            self.store.set_pending_selection(chat_id, None)
            self._reply(
                chat_id,
                "Here are all the options again:\n\n"
                + HELP_TEXT,
            )
        elif command == "/reset":
            logger.info("Chat %s reset all settings.", chat_id)
            self.store.clear(chat_id)
            self._notify_change(chat_id)
            self._reply(chat_id, "Removed all your dates and timings. Set new ones with /setdate.")
        else:
            logger.info("Chat %s sent non-command text; treating as selection.", chat_id)
            self._handle_timing_selection(chat_id, text)

    def _set_date(self, chat_id, arg: str) -> None:
        dates = parse_dates(arg)
        if not dates:
            logger.warning("Chat %s sent unparsable dates: %r", chat_id, arg)
            self._reply(
                chat_id,
                "Couldn't read those dates. Use the format: /setdate 15-08-2026, 16-08-2026",
            )
            return

        iso_dates = [d.isoformat() for d in dates]
        self.store.set_dates(chat_id, iso_dates)
        self.store.set_timings(chat_id, [])
        self.store.set_pending_selection(chat_id, None)

        pretty = ", ".join(d.strftime("%d-%m-%Y") for d in dates)
        logger.info("Chat %s now tracking dates: %s", chat_id, ", ".join(iso_dates))
        self._notify_change(chat_id)
        self._reply(
            chat_id,
            f"Tracking these dates: {pretty}\n\n"
            "Run /settime to pick your preferred showtimes "
            "(or skip it to be alerted on any booking).",
        )

    def _set_timings(self, chat_id) -> None:
        dates = self.store.dates(chat_id)
        if not dates:
            logger.warning("Chat %s ran /settime without dates.", chat_id)
            self._reply(chat_id, "Set dates first: /setdate 15-08-2026")
            return

        options = []
        for iso in dates:
            logger.info("Fetching showtimes for %s (chat %s)...", iso, chat_id)
            try:
                times = self.scraper.fetch_showtimes(iso.replace("-", ""))
            except Exception as exc:
                logger.exception(
                    "Timings fetch failed for %s (chat %s)", iso, chat_id
                )
                self._reply(
                    chat_id,
                    f"Couldn't load showtimes for {_short_date(iso)}. Try again in a bit.",
                )
                return
            logger.info("Showtimes for %s: %s", iso, ", ".join(times) or "none")
            for time_str in times:
                options.append({"iso": iso, "time": time_str})

        if not options:
            logger.info("No open bookings for any date (chat %s).", chat_id)
            self._reply(
                chat_id,
                "No bookings open yet for any of your dates. I'll keep watching - "
                "run /settime again later.",
            )
            return

        logger.info("Showing %d timing options to chat %s.", len(options), chat_id)
        self.store.set_pending_selection(chat_id, {"options": options, "selected": []})
        self._send_picker(chat_id, options, [])

    def _handle_timing_selection(self, chat_id, text: str) -> None:
        pending = self.store.pending_selection(chat_id)
        if not pending or not isinstance(pending, dict):
            logger.warning("Chat %s sent '%s' but no pending selection.", chat_id, text)
            self._reply(chat_id, "Unknown command. Try /help")
            return

        options = pending["options"]
        indices = parse_selection(text, len(options))
        if not indices:
            logger.warning(
                "Chat %s sent invalid selection '%s' (max %d).",
                chat_id, text, len(options),
            )
            self._reply(chat_id, "I didn't understand that. Reply with numbers like 1,3")
            return

        timings = sorted({options[i - 1]["time"] for i in indices})
        self.store.set_timings(chat_id, timings)
        self.store.set_pending_selection(chat_id, None)
        logger.info("Chat %s selected timings: %s", chat_id, ", ".join(timings))
        self._notify_change(chat_id)
        self._reply(chat_id, f"Got it. I'll alert you for: {', '.join(timings)}")

    def _set_notify(self, chat_id, arg: str) -> None:
        """Handle /notify once|every [minutes]."""
        arg = arg.strip().lower()
        if arg in ("once", "1", "one", "single"):
            self.store.set_notify(chat_id, "once", None)
            logger.info("Chat %s set notify mode to once.", chat_id)
            self._notify_change(chat_id)
            self._reply(
                chat_id,
                "Got it. I'll alert you only once when bookings open "
                "(and again if they close and reopen).",
            )
            return

        match = re.match(r"every(?:\s+(\d+))?", arg)
        if match:
            minutes = int(match.group(1)) if match.group(1) else None
            self.store.set_notify(chat_id, "every", minutes)
            logger.info(
                "Chat %s set notify mode to every%s.",
                chat_id,
                f" {minutes}m" if minutes else " cycle",
            )
            self._notify_change(chat_id)
            if minutes:
                self._reply(
                    chat_id,
                    f"Got it. I'll alert you every {minutes} minute(s) while bookings stay open.",
                )
            else:
                self._reply(
                    chat_id,
                    "Got it. I'll alert you on every check cycle while bookings stay open.",
                )
            return

        self._reply(
            chat_id,
            "Usage:\n"
            "/notify once - alert me only once\n"
            "/notify every - alert me every check cycle\n"
            "/notify every 30 - alert me every 30 minutes",
        )

    def _status(self, chat_id) -> None:
        dates = self.store.dates(chat_id)
        if not dates:
            self._reply(chat_id, "No dates set yet. Use /setdate 15-08-2026")
            return

        pretty_dates = ", ".join(_short_date(d) for d in dates)
        timings = self.store.timings(chat_id)
        pretty_timings = ", ".join(timings) if timings else "any booking"
        mode = self.store.notify_mode(chat_id)
        interval = self.store.notify_interval_minutes(chat_id)
        if mode == "every":
            pretty_notify = (
                f"every {interval} min" if interval else "every check cycle"
            )
        else:
            pretty_notify = "once when open"
        logger.info(
            "Status for chat %s: dates=[%s] timings=[%s] notify=[%s]",
            chat_id, pretty_dates, pretty_timings, pretty_notify,
        )
        self._reply(
            chat_id,
            f"Check cycle: {self._interval_text()}\n"
            f"Dates: {pretty_dates}\n"
            f"Alert for: {pretty_timings}\n"
            f"Notify: {pretty_notify}",
        )

    # ------------------------------------------------------------- inline picker

    def _send_picker(self, chat_id, options, selected, message_id=None) -> None:
        lines = []
        for i, opt in enumerate(options):
            mark = "\u2611\ufe0f " if i in selected else ""
            lines.append(f"{i + 1}. {mark}{_short_date(opt['iso'])} - {opt['time']}")
        text = "Select the showtimes you want, then tap Done:\n\n" + "\n".join(lines)
        text += "\n\n(Or reply with numbers like 1,3)"

        markup = self._markup(options, selected)
        if message_id:
            self._post(
                "editMessageText",
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup,
            )
        else:
            self._post("sendMessage", chat_id=chat_id, text=text, reply_markup=markup)

    @staticmethod
    def _markup(options, selected) -> dict:
        rows = []
        for i, opt in enumerate(options):
            mark = "\u2611\ufe0f " if i in selected else ""
            label = f"{mark}{_short_date(opt['iso'])} - {opt['time']}"
            rows.append([{"text": label, "callback_data": f"pick:{i}"}])
        rows.append(
            [
                {"text": "Done", "callback_data": "done"},
                {"text": "Cancel", "callback_data": "cancel"},
            ]
        )
        return {"inline_keyboard": rows}

    def _handle_callback_query(self, callback_query) -> None:
        qid = callback_query["id"]
        chat_id = (callback_query.get("message") or {}).get("chat", {}).get("id")
        message_id = (callback_query.get("message") or {}).get("message_id")
        data = callback_query.get("data", "")
        if not chat_id:
            return

        self._post("answerCallbackQuery", callback_query_id=qid)

        pending = self.store.pending_selection(chat_id)
        if not pending or not isinstance(pending, dict):
            if data == "done":
                logger.info(
                    "Chat %s tapped Done again (already saved); ignoring.", chat_id
                )
                self._post(
                    "answerCallbackQuery",
                    callback_query_id=qid,
                    text="Already saved",
                    show_alert=False,
                )
            else:
                logger.info(
                    "Stale callback %r from chat %s; ignoring.", data, chat_id
                )
            return

        options = pending["options"]
        selected = list(pending["selected"])

        if data == "done":
            timings = sorted({options[i]["time"] for i in selected})
            self.store.set_timings(chat_id, timings)
            self.store.set_pending_selection(chat_id, None)
            summary = ", ".join(timings) if timings else "any booking"
            logger.info(
                "Chat %s tapped Done; saved timings: %s", chat_id, summary
            )
            self._notify_change(chat_id)
            self._post(
                "editMessageText",
                chat_id=chat_id,
                message_id=message_id,
                text=f"Got it. I'll alert you for: {summary}",
            )
        elif data == "cancel":
            logger.info("Chat %s cancelled the timing picker.", chat_id)
            self.store.set_pending_selection(chat_id, None)
            self._post(
                "editMessageText",
                chat_id=chat_id,
                message_id=message_id,
                text="Cancelled.",
            )
        elif data.startswith("pick:"):
            idx = int(data.split(":", 1)[1])
            if idx in selected:
                selected.remove(idx)
                action = "deselected"
            else:
                selected.append(idx)
                action = "selected"
            selected.sort()
            pending["selected"] = selected
            self.store.set_pending_selection(chat_id, pending)
            logger.info(
                "Chat %s %s option %d (%s); current selection: %s",
                chat_id, action, idx, options[idx]["time"], selected,
            )
            self._send_picker(chat_id, options, selected, message_id=message_id)


__all__ = ["TelegramBot", "parse_dates", "parse_selection"]
