#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-08 14:28:09 krylon>
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
from threading import RLock
from typing import Final, Optional

from simplebayes import SimpleBayes

from headlines import common
from headlines.cache import Cache, CacheDB, DBType
from headlines.database import Database
from headlines.model import Item, Rating
from headlines.nlp import NLP

cache_file: Final[str] = "classifier.pickle"


@dataclass(kw_only=True, slots=True)
class Karl:
    """Karl classifies Items as boring or interesting.

    Get it? Karl, because Karl Marx and class struggle? I'll see myself out.
    """

    log: logging.Logger = field(default_factory=lambda: common.get_logger("karl"))
    lock: RLock = field(default_factory=RLock)
    nlp: NLP = field(default_factory=NLP)
    bayes: SimpleBayes = \
        field(default_factory=lambda: SimpleBayes(cache_path=str(common.path.cache)))
    _cache: CacheDB = field(init=False)

    def __post_init__(self) -> None:
        self.log.info("Hello from Karl's constructor.")
        self._cache = Cache().get_db(DBType.Rating, 3600)
        self.bayes.cache_file = cache_file
        if not self.has_cache() or not self.bayes.cache_train():
            self.retrain()

    def retrain(self) -> None:
        """Retrain the Bayes net from the database."""
        self.log.info("Training Classifier")
        db: Database = Database()
        try:
            items: list[Item] = db.item_get_rated()
            with self.lock:
                self.bayes.flush()
                self._cache.purge(True)

                for item in items:
                    txt: str = self.nlp.preprocess(item)
                    if item.rating != Rating.Unrated:
                        self.bayes.train(item.rating.name, txt)

                self.bayes.cache_persist()
        finally:
            db.close()

    def has_cache(self) -> bool:
        """Return True if a file with cached training data exists."""
        loc: Final[str] = self.bayes.get_cache_location()
        self.log.info("Advisor cache is %s", loc)
        return os.path.exists(loc)

    def classify(self, item: Item) -> Rating:
        """Classify an Item based on trained data."""
        if item.is_rated:
            return item.rating
        xid: Final[str] = item.xid
        with self.lock:
            with self._cache.tx(False) as tx:
                rstr: Optional[str] = tx[xid]
            if rstr is None:
                txt: Final[str] = self.nlp.preprocess(item)
                rstr = self.bayes.classify(txt)
                with self._cache.tx(True) as tx:
                    tx[xid] = rstr
        rating: Final[Rating] = Rating.from_str(rstr)
        item.cache_rating(rating)
        return rating

    def learn(self, item: Item, rating: Rating) -> None:
        """Add an Item and its Rating to the training data."""
        xid: Final[str] = item.xid
        with self.lock:
            try:
                txt: Final[str] = self.nlp.preprocess(item)
                with self._cache.tx(True) as tx:
                    del tx[xid]
                match rating:
                    case Rating.Boring | Rating.Interesting:
                        self.bayes.train(rating.name, txt)
                    case Rating.Unrated:
                        assert item.rating != Rating.Unrated
                        self.bayes.untrain(item.rating, txt)
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
