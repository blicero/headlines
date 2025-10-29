#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-29 16:43:30 krylon>
#
# /data/code/python/headlines/tagging.py
# created on 26. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.tagging

(c) 2025 Benjamin Walkenhorst
"""


import logging
import os
from dataclasses import dataclass, field
from threading import Lock
from typing import Final

from simplebayes import SimpleBayes

from headlines import common
from headlines.database import Database
from headlines.model import Item, Tag

cache_file: Final[str] = "advisor.pickle"


@dataclass(kw_only=True, slots=True)
class Advisor:
    """Advisor suggests Tags for Items."""

    log: logging.Logger = field(default_factory=lambda: common.get_logger("advisor"))
    lock: Lock = field(default_factory=Lock)
    bayes: SimpleBayes = \
        field(default_factory=lambda: SimpleBayes(cache_path=str(common.path.cache)))
    tag_cache: dict[str, Tag] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.log.info("Hello from Advisor's constructor")
        self.bayes.cache_file = cache_file
        db: Database = Database()
        try:
            tags = db.tag_get_all()
        finally:
            db.close()

        for tag in tags:
            self.tag_cache[tag.name] = tag

        if not self.has_cache() or not self.bayes.cache_train():
            self.retrain()

    def has_cache(self) -> bool:
        """Return True if a file with cached training data exists."""
        loc: Final[str] = self.bayes.get_cache_location()
        self.log.info("Advisor cache is %s", loc)
        return os.path.exists(loc)

    def retrain(self) -> None:
        """Retrain the Bayes net from the database."""
        self.log.info("Training Tag Advisor")
        db: Database = Database()
        try:
            items: list[Item] = db.tag_link_get_tagged_items()
            with self.lock:
                self.bayes.flush()

                for item in items:
                    tags = db.tag_link_get_by_item(item)

                    for tag in tags:
                        self.bayes.train(tag.name, item.clean_full)

                self.bayes.cache_persist()
        finally:
            db.close()

    def learn(self, item: Item, tag: Tag) -> None:
        """Learn about a new Item-Tag link."""
        with self.lock:
            self.bayes.train(tag.name, item.clean_full)

    def forget(self, item: Item, tag: Tag) -> None:
        """Remove the association between <item> and <tag>."""
        with self.lock:
            self.bayes.untrain(tag.name, item.clean_full)

    def save(self) -> None:
        """Save the training state."""
        with self.lock:
            self.bayes.cache_persist()

    def advise(self, item: Item, cnt: int = 10) -> list[tuple[Tag, float]]:
        """Return up to <cnt> Tags best matching <item>."""
        assert cnt > 0
        with self.lock:
            scores: Final[dict[str, float]] = self.bayes.score(item.clean_full)

        tags = [(self.tag_cache[x[0]], x[1]) for x in scores.items()]

        tags.sort(key=lambda x: x[1], reverse=True)

        if len(tags) > cnt:
            tags = tags[:cnt]

        return tags

# Local Variables: #
# python-indent: 4 #
# End: #
