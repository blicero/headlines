#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-17 16:29:38 krylon>
#
# /data/code/python/headlines/classy.py
# created on 15. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.classy

(c) 2025 Benjamin Walkenhorst
"""


import logging
import os
from dataclasses import dataclass, field
from threading import Lock
from typing import Final

from bs4 import BeautifulSoup
from simplebayes import SimpleBayes

from headlines import common
from headlines.model import Item, Rating


@dataclass(kw_only=True, slots=True)
class Karl:
    """Karl classifies Items as boring or interesting.

    Get it? Karl, because Karl Marx and class struggle? I'll see myself out.
    """

    log: logging.Logger = field(default_factory=lambda: common.get_logger("Karl"))
    lock: Lock = field(default_factory=Lock)
    bayes: SimpleBayes = \
        field(default_factory=lambda: SimpleBayes(cache_path=str(common.path.cache)))

    def __post_init(self) -> None:  # pylint: disable-msg=W0238
        if not self.bayes.cache_train():
            self.log.error("Failed to train classifier")

    def has_cache(self) -> bool:
        """Return True if a file with cached training data exists."""
        # full_path = common.path.spool.joinpath(self.bayes.cache_file)
        # return full_path.exists()
        return os.path.exists(self.bayes.get_cache_location())

    def item_text(self, item: Item) -> str:
        """Return the plain text from an Item."""
        # TODO Maybe add some caching later on.
        raw: Final[str] = item.headline + " " + item.body
        soup = BeautifulSoup(raw, "html.parser")
        plain: Final[str] = soup.get_text()
        return plain.lower()

    def classify(self, item: Item) -> Rating:
        """Classify an Item based on trained data."""
        with self.lock:
            plain = self.item_text(item)
            rating: Final[Rating] = Rating.from_str(self.bayes.classify(plain))
            item.cache_rating(rating)
            return rating

    def train_bulk(self, items: list[Item]) -> None:
        """Train the classifier on a list of Items."""
        with self.lock:
            self.bayes.flush()
            for item in items:
                if item.rating == Rating.Unrated:
                    continue
                plain: str = self.item_text(item)
                self.bayes.train(item.rating.name, plain)
            self.bayes.cache_persist()

    def learn(self, item: Item, rating: Rating) -> None:
        """Add an Item and its Rating to the training data."""
        with self.lock:
            try:
                plain = self.item_text(item)
                match rating:
                    case Rating.Boring | Rating.Interesting:
                        self.bayes.train(rating.name, plain)
                    case Rating.Unrated:
                        assert item.rating != Rating.Unrated
                        self.bayes.untrain(item.rating, plain)  # ???
            except Exception as err:  # pylint: disable-msg=W0718
                cname: Final[str] = err.__class__.__name__
                self.log.error("%s trying to train on Item %d (%s): %s",
                               cname,
                               item.item_id,
                               item.headline,
                               err)
            else:
                item.rating = rating
                self.bayes.cache_persist()


# Local Variables: #
# python-indent: 4 #
# End: #
