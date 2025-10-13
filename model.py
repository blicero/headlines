#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-13 23:07:31 krylon>
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


from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from headlines import common


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


@dataclass(kw_only=True, slots=True)
class Item:
    """Item is a news item from an RSS feed."""

    item_id: int = 0
    feed_id: int
    url: str
    headline: str
    body: str
    timestamp: datetime

    @property
    def stamp_str(self) -> str:
        """Return the Item's timestamp as a properly formatted string."""
        return self.timestamp.strftime(common.TimeFmt)


@dataclass(kw_only=True, slots=True)
class Tag:
    """Tag is a short piece of text attached to Items."""

    tag_id: int = 0
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
