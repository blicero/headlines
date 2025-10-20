#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-18 21:21:39 krylon>
#
# /data/code/python/headlines/src/headlines/engine.py
# created on 30. 09. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.engine

(c) 2025 Benjamin Walkenhorst

Engine implements the downloading and processing of RSS feeds.
"""


import logging
import time
from datetime import datetime, timedelta
from queue import Empty, SimpleQueue
from threading import Lock, Thread
from typing import Final, Union

from easy_rss import EasyRSS  # type: ignore # pylint: disable-msg=E0401

from headlines import common
from headlines.database import Database
from headlines.model import Feed, Item

qtimeout: Final[int] = 5
worker_count: int = 8


class Engine:
    """Fetcher downloads RSS feeds."""

    __slots__ = [
        "log",
        "db",
        "interval",
        "lock",
        "_active",
        "feedq",
        "itemq",
    ]

    log: logging.Logger
    db: Database
    interval: timedelta
    lock: Lock
    _active: bool
    feedq: SimpleQueue
    itemq: SimpleQueue

    def __init__(self, interval: Union[int, float, timedelta]) -> None:
        self.log = common.get_logger("engine")
        self.db = Database()
        self.lock = Lock()
        self._active = False
        self.feedq = SimpleQueue()
        self.itemq = SimpleQueue()
        match interval:
            case int(x):
                self.interval = timedelta(seconds=x)
            case float(x):
                self.interval = timedelta(seconds=x)
            case x if isinstance(x, timedelta):
                self.interval = x
            case _:
                name = interval.__class__.__name__
                msg = f"Interval must be a number (of seconds) or a timedelta, not a {name}"
                raise ValueError(msg)

        self.log.debug("Engine will check for news every %s seconds.",
                       self.interval.seconds)

    @property
    def active(self) -> bool:
        """Return the Engine's active flag."""
        with self.lock:
            return self._active

    @active.setter
    def active(self, value: bool) -> None:
        """Set the Engine's active flag."""
        with self.lock:
            self._active = value

    def start(self) -> None:
        """Begin to periodically check the datbase for Feeds due for a refresh."""
        self.log.debug("Engine is starting.")
        self.active = True

        iloop: Thread = Thread(name="Item Catcher", target=self._item_loop, daemon=True)
        iloop.start()

        for i in range(worker_count):
            idx: int = i+1
            w: Thread = Thread(name=f"Fetcher{idx:02d}",
                               target=self._fetch_loop,
                               args=(idx, ),
                               daemon=True)
            w.start()

        feeder: Thread = Thread(name="Feeder", target=self._feeder_loop, daemon=True)
        feeder.start()

    def _feeder_loop(self) -> None:
        """Periodically load all pending Feeds and feed them to the Feed queue."""
        self.log.debug("Feeder loop is starting up.")
        try:
            db: Database = Database()
            while self.active:
                feeds: list[Feed] = db.feed_get_pending()
                if len(feeds) > 0:
                    names = ", ".join([x.name for x in feeds])
                    self.log.debug("Feeder is about to dispatch %d feeds: %s",
                                   len(feeds),
                                   names)
                for f in feeds:
                    self.feedq.put(f)
                time.sleep(self.interval.total_seconds())
        finally:
            self.log.debug("Feeder loop is quitting.")
            db.close()

    def _fetch_loop(self, num: int) -> None:
        """Fetch pending Feeds as they come in through the Feed queue."""
        self.log.debug("Fetch worker %02d is starting up.", num)
        while self.active:
            try:
                feed: Feed = self.feedq.get(True, qtimeout)
                self.log.debug("Fetch worker %02d is about to fetch Feed %s (%d / %s)",
                               num,
                               feed.name,
                               feed.fid,
                               feed.url)
                rss = EasyRSS(feed.url)

                db: Database = Database()
                db.feed_set_last_update(feed, datetime.now())
                db.close()

                self.log.debug("Fetch worker %02d got %d items from %s",
                               num,
                               len(rss.articles),
                               feed.name)
                for art in rss.articles:
                    # For the love of Goat, why don't they use ISO 8601 like sane people?!?!?!
                    # Sample: Oct 14, 2025 11:25AM
                    # self.log.debug("Fetch worker %02d: Item '%s' was published %s",
                    #                num,
                    #                art.title,
                    #                art.pubDate)
                    timestamp: datetime = datetime.strptime(art.pubDate,
                                                            "%b %d, %Y %I:%M%p")
                    item: Item = Item(
                        feed_id=feed.fid,
                        url=art.link,
                        headline=art.title,
                        body=art.description,
                        timestamp=timestamp,
                    )

                    self.itemq.put(item)
            except Empty:
                continue
        self.log.debug("Fetch worker %02d is quitting.", num)

    def _item_loop(self) -> None:
        """Get the Items from the Queue, put them in the database."""
        self.log.debug("Item worker going online...")
        db: Database = Database()
        while self.active:
            try:
                item: Item = self.itemq.get(True, qtimeout)
                with db:
                    other = db.item_get_by_url(item.url)
                    if other is not None:
                        continue
                    self.log.debug("Caught one item: %s - %s (%s)",
                                   item.headline,
                                   item.stamp_str,
                                   item.url,)
                    db.item_add(item)
            except Empty:
                continue
        self.log.debug("Item catcher is done. Byeeeeeee")


# Local Variables: #
# python-indent: 4 #
# End: #
