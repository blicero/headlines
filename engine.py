#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-24 20:45:38 krylon>
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


import inspect
import logging
import time
from datetime import datetime, timedelta
from queue import Empty, SimpleQueue
from threading import Lock, Thread
from typing import Final, Optional, Union

import fastfeedparser as ffp  # type: ignore # pylint: disable-msg=E0401

from headlines import common
from headlines.database import Database
from headlines.model import Feed, Item

timepat: Final[str] = "%Y-%m-%dT%H:%M:%S%z"
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
                # rss = EasyRSS(feed.url)
                rss = ffp.parse(feed.url)

                db: Database = Database()
                db.feed_set_last_update(feed, datetime.now())
                db.close()

                self.log.debug("Fetch worker %02d got %d items from %s",
                               num,
                               len(rss.entries),
                               feed.name)
                for art in rss.entries:
                    # For the love of Goat, why don't they use ISO 8601 like sane people?!?!?!
                    # Sample: Oct 14, 2025 11:25AM
                    # self.log.debug("Fetch worker %02d: Item '%s' was published %s",
                    #                num,
                    #                art.title,
                    #                art.pubDate)
                    # 24. 10. 2025
                    # Apparently, The Register's Atom feed has no pubDate. I don't know if this
                    # a just their feed or if it's Atom in general.
                    try:
                        # timestamp: datetime = datetime.strptime(art.pubDate,
                        #                                         "%b %d, %Y %I:%M%p")
                        timestamp: datetime = datetime.strptime(art.published, timepat)

                        # if not isinstance(art.content, str):
                        #     self.log.info("Content of article '%s' is not a string, but %s\n%s",
                        #                   art.title,
                        #                   art.content.__class__.__name__,
                        #                   art.content)

                        item: Item = Item(
                            feed_id=feed.fid,
                            url=art.link,
                            headline=art.title,
                            body=self._item_description(art),
                            timestamp=timestamp,
                        )

                        self.itemq.put(item)
                    except AttributeError as err:
                        members: str = ", ".join([f"{x[0]} = {x[1]}"
                                                  for x in inspect.getmembers(art)
                                                  if not x[0].startswith("_")])
                        self.log.error("AttributeError: in Item from %s: %s\n\n%s",
                                       feed.name,
                                       err,
                                       members)
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

    def _item_description(self, article) -> str:
        """Try to get a description/summary from an Atom/RSS item."""
        desc: str = ""
        if hasattr(article, 'description'):
            desc = article.description
        elif hasattr(article, 'content'):
            desc = article.content[0]['value']
        else:
            self.log.info("Did not find description or summary in article \"%s\"",
                          article.title)

        return desc

    def _item_timestamp(self, article) -> datetime:
        """Try to get a timestamp from an Atom or RSS item."""
        stamp: Optional[datetime] = None
        timestr: str = ""
        if hasattr(article, 'pubDate'):
            timestr = article.pubDate
        elif hasattr(article, 'published'):
            timestr = article.published

        if timestr != "":
            stamp = datetime.strptime(timestr, timepat)
        else:
            self.log.info("Did not find timestamp in Item, using current time.")
            stamp = datetime.now()

        return stamp


# Local Variables: #
# python-indent: 4 #
# End: #
