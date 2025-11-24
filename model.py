#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-24 18:32:49 krylon>
#
# /data/code/python/headlines/src/headlines/model.py
# created on 30. 09. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.model

(c) 2025 Benjamin Walkenhorst
"""


import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from threading import RLock
from typing import Final, Optional, Union

import langdetect
from bs4 import BeautifulSoup
from krylib import Singleton

from headlines import common
from headlines.scrub import Scrubber


@dataclass(kw_only=True, slots=True)
class Feed:
    """Feed is an RSS/Atom feed we subscribe to."""

    fid: int = 0
    url: str
    homepage: str = ""
    name: str
    description: str = ""
    interval: int = 1800  # Interval in seconds to refresh the feed
    last_update: Optional[datetime] = None
    active: bool = True

    @property
    def interval_str(self) -> str:
        """Return a human-readable representation of the Feed's refresh interval."""
        seconds: int = self.interval
        minutes: int = 0
        hours: int = 0

        if seconds > 3600:
            hours, seconds = divmod(seconds, 3600)

        if seconds > 60:
            minutes, seconds = divmod(seconds, 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def update_str(self) -> str:
        """Return the last_update formated as a human-readable string.

        If last_update is None, return an empty string.
        """
        if self.last_update is None:
            return ""
        return self.last_update.strftime(common.TimeFmt)


class Rating(IntEnum):
    """Rating describes the rating for a news Item."""

    Unrated = -1
    Boring = 0
    Interesting = 1

    @classmethod
    def from_str(cls, name: Optional[str]) -> 'Rating':
        """Create a Rating from its string value."""
        if name is None:
            return cls.Unrated
        match name.lower():
            case "unrated":
                return cls.Unrated
            case "boring":
                return cls.Boring
            case "interesting":
                return cls.Interesting
            case _:
                raise ValueError(f"Invalid Rating name '{name}'")


@dataclass(kw_only=True, slots=True)
class Item:
    """Item is a news item from an RSS feed."""

    item_id: int = 0
    feed_id: int
    url: str
    headline: str
    body: str
    timestamp: datetime
    time_added: datetime = field(default_factory=datetime.now)
    rating: Rating = Rating.Unrated
    _cached_rating: Optional[tuple[Rating, float]] = None

    @property
    def is_rated(self) -> bool:
        """Return True if the Item has been rated by the user."""
        return self.rating != Rating.Unrated

    @property
    def effective_rating(self) -> Rating:
        """Return the manual or cached Rating for the news Item."""
        if self.rating != Rating.Unrated:
            return self.rating
        if self._cached_rating is not None:
            return self._cached_rating[0]
        return Rating.Unrated

    def cache_rating(self, rating: Rating, score: Optional[float] = None) -> None:
        """Cache a generated Rating for the Item."""
        self._cached_rating = (rating,
                               score if score is not None else 1.0)

    @property
    def stamp_str(self) -> str:
        """Return the Item's timestamp as a properly formatted string."""
        return self.timestamp.strftime(common.TimeFmt)

    @property
    def string(self) -> str:
        """Return a minimal string representation of the Item."""
        # pylint: disable-msg=C0209
        return "Item(item_id={}, url='{}', headline='{}', timestamp='{}')".format(
            self.item_id,
            self.url,
            self.headline,
            self.stamp_str,
        )

    @property
    def clean_body(self) -> str:
        """Return a sanitized copy of the Item's body."""
        scrubber: Scrubber = Scrubber()
        return scrubber.scrub_html(self.body, self.item_id)

    @property
    def clean_full(self) -> str:
        """Return a sanitized copy of the Item's headline and body."""
        return self.headline + " " + self.clean_body

    @property
    def plain_body(self) -> str:
        """Return a copy of the Item's body stripped of all HTML elements."""
        soup = BeautifulSoup(self.body, "html.parser")
        plain: Final[str] = soup.get_text()
        return plain

    @property
    def plain_full(self) -> str:
        """Return a string that is the concatenation of the Item's headline and stripped body."""
        return self.headline + " " + self.plain_body

    @property
    def language(self) -> str:
        """Attempt to guess which language the Item is written in."""
        return langdetect.detect(self.plain_full)

    @property
    def xid(self) -> str:
        """Return the Item ID stringified, suitable as a key for caching."""
        return f"{self.item_id:08x}"


@dataclass(kw_only=True, slots=True, eq=True, unsafe_hash=True)
class Tag:
    """Tag is a short piece of text attached to Items."""

    tag_id: int = 0
    parent: Optional[int] = None
    name: str
    description: str = ""
    lvl: int = 0
    full_name: str = ""
    link_cnt: int = 0
    link_cnt_rec: int = 0


@dataclass(kw_only=True, slots=True)
class TagLink:
    """TagLink affixes a Tag to an Item."""

    lid: int = 0
    tag_id: int
    item_id: int


@dataclass(kw_only=True, slots=True, unsafe_hash=True)
class Later:
    """Later signifies that a news Item is to be read at a later time."""

    lid: int = 0
    item_id: int = 0
    time_marked: datetime = field(default_factory=datetime.now)
    time_finished: Optional[datetime] = None

    @property
    def finished(self) -> bool:
        """Return True if the Item has been marked as read."""
        return self.time_finished is not None

    @property
    def marked_str(self) -> str:
        """Return the time_marked timestamp as a human-readable string."""
        return self.time_marked.strftime(common.TimeFmt)

    @property
    def finished_str(self) -> str:
        """Return the time_finished timestamp as a human-readable string.

        If the Item has not been marked finished, and the time_finished field is
        None, return an empty string.
        """
        if self.time_finished is not None:
            return self.time_finished.strftime(common.TimeFmt)
        return ""


@dataclass(kw_only=True, slots=True)
class BlacklistItem:
    """An item in the Blacklist."""

    item_id: int
    pattern: re.Pattern
    cnt: int = 0

    def matches(self, item: Union[str, Item]) -> bool:
        """Return True if the Item is matched by the BlacklistItem's pattern."""
        # WTF, pylint?
        txt: Final[str] = item if isinstance(item, str) else item.plain_full
        match self.pattern.search(txt):  # pylint: disable-msg=E1101
            case None:
                return False
            case _:
                self.cnt += 1
                return True


@dataclass(kw_only=True, slots=True)
class Blacklist(metaclass=Singleton):
    """Blacklist represents a list of regex patterns to filter unwanted Items."""

    log: logging.Logger = field(default_factory=lambda: common.get_logger("blacklist"))
    lock: RLock = field(default_factory=RLock)
    items: list[BlacklistItem] = field(init=False)

    def __post_init__(self) -> None:
        pass

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, _ex_type, _ex_val, _trace):
        self.lock.release()

    def sort(self) -> None:
        """Sort the Blacklist's Items according to their count."""
        with self.lock:
            self.items.sort(key=lambda x: x.cnt, reverse=True)

    def matches(self, txt: Union[str, Item]) -> bool:
        """Attempt to match an Item against the blacklist."""
        if isinstance(txt, Item):
            txt = txt.plain_full

        with self.lock:
            for i in self.items:
                if i.matches(txt):
                    self.sort()
                    return True

        return False

# Local Variables: #
# python-indent: 4 #
# End: #
