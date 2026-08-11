"""Entry point: runs the Telegram bot and the booking tracker together."""

import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bms_tracker import config
from bms_tracker.bot import TelegramBot
from bms_tracker.notifier import Notifier
from bms_tracker.scraper import BMSScraper
from bms_tracker.store import Store
from bms_tracker.tracker import Tracker


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server convention)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args) -> None:  # silence request logs
        pass


def _start_health_server(port: int) -> ThreadingHTTPServer:
    """Serve a minimal / health endpoint for container platforms."""
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("bms-tracker")

    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Check the .env file.")
        return

    store = Store(config.DATA_FILE)
    scraper = BMSScraper()
    notifier = Notifier(config.TELEGRAM_BOT_TOKEN)

    health_port = os.getenv("BMS_HEALTH_PORT")
    if health_port:
        try:
            _start_health_server(int(health_port))
            logger.info("Health server listening on port %s.", health_port)
        except (ValueError, OSError) as exc:
            logger.warning("Could not start health server on port %s: %s", health_port, exc)

    tracker = Tracker(store, notifier, scraper, config.INTERVAL_SECONDS)

    bot = TelegramBot(
        config.TELEGRAM_BOT_TOKEN,
        store,
        scraper,
        notifier,
        on_change=tracker.on_config_changed,
        interval_seconds=config.INTERVAL_SECONDS,
    )

    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()

    def shutdown(_signum, _frame) -> None:
        logger.info("Shutting down...")
        tracker.stop()
        bot.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        tracker.run()
    except KeyboardInterrupt:
        tracker.stop()
        bot.stop()
    finally:
        logger.info("Exiting.")


if __name__ == "__main__":
    main()
