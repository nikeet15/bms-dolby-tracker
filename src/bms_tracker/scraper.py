"""BookMyShow venue page scraper."""

import logging
import re
from datetime import date
from typing import List, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from bms_tracker import config

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)


class BMSScraper:
    def __init__(self, venue_url: Optional[str] = None) -> None:
        self.venue_url = venue_url or self.url_for(date.today().strftime("%Y%m%d"))

    @staticmethod
    def url_for(day: str) -> str:
        """Build the venue URL for a YYYYMMDD day string."""
        return config.VENUE_URL + day

    def fetch_page(self, url: Optional[str] = None) -> str:
        return self._load_page(url)[0]

    def _load_page(self, url: Optional[str] = None):
        """Load a page and return (html, final_url) after any redirects."""
        target = url or self.venue_url
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    locale="en-US",
                    viewport={"width": 1440, "height": 900},
                    timezone_id="Asia/Kolkata",
                )
                page = context.new_page()
                page.goto(target, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(8000)
                return page.content(), page.url
            finally:
                browser.close()

    def _bookable_labels(self, day: Optional[str] = None) -> List[str]:
        url = self.url_for(day) if day else self.venue_url
        html, final_url = self._load_page(url)
        if day and not final_url.rstrip("/").endswith(day):
            logger.info(
                "Date %s not available yet; redirected to %s", day, final_url
            )
            return []
        soup = BeautifulSoup(html, "html.parser")
        return [
            b.get("aria-label", "")
            for b in soup.select('[role="button"][aria-label^="Book "]')
        ]

    def check_showtimes(self, day: Optional[str] = None) -> bool:
        return bool(self._bookable_labels(day))

    def fetch_showtimes(self, day: Optional[str] = None) -> List[str]:
        """Return sorted unique showtimes (e.g. ['07:00 PM', '09:00 PM'])."""
        times = set()
        for label in self._bookable_labels(day):
            match = TIME_RE.search(label)
            if match:
                times.add(match.group(1).upper())
        return sorted(times)


__all__ = ["BMSScraper"]
