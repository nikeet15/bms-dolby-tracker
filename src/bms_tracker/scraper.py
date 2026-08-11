"""BookMyShow venue page scraper."""

import logging
import re
from datetime import date
from typing import List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from bms_tracker import config

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)


class BMSScraper:
    def __init__(self, venue_url: Optional[str] = None) -> None:
        self.venue_url = venue_url or self.url_for(date.today().strftime("%Y%m%d"))

    @staticmethod
    def url_for(day: str) -> str:
        """Build the venue URL for a YYYYMMDD day string."""
        return config.VENUE_URL + day

    def _load_page(self, url: Optional[str] = None):
        """Load a page and return (html, final_url) after any redirects."""
        target = url or self.venue_url
        response = cffi_requests.get(
            target,
            impersonate="chrome",
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
            },
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text, str(response.url)

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

    def fetch_showtimes(self, day: Optional[str] = None) -> List[str]:
        """Return sorted unique showtimes (e.g. ['07:00 PM', '09:00 PM'])."""
        times = set()
        for label in self._bookable_labels(day):
            match = TIME_RE.search(label)
            if match:
                times.add(match.group(1).upper())
        return sorted(times)


__all__ = ["BMSScraper"]
