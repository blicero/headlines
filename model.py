#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-20 13:31:20 krylon>
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


from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional

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


@dataclass(kw_only=True, slots=True, eq=True, unsafe_hash=True)
class Tag:
    """Tag is a short piece of text attached to Items."""

    tag_id: int = 0
    parent: Optional[int] = None
    name: str
    description: str = ""


@dataclass(kw_only=True, slots=True)
class TagLink:
    """TagLink affixes a Tag to an Item."""

    lid: int = 0
    tag_id: int
    item_id: int


# Local Variables: #
# python-indent: 4 #
# End: #
