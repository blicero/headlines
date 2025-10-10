#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-10 17:41:24 krylon>
#
# /data/code/python/headlines/src/headlines/database.py
# created on 30. 09. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.database

(c) 2025 Benjamin Walkenhorst
"""


import logging
import math
import sqlite3
from datetime import datetime
from enum import Enum, auto
from threading import Lock
from typing import Final, Optional

import krylib

from headlines import common
from headlines.model import Feed, Item

qinit: Final[list[str]] = [
    """
CREATE TABLE feed (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    homepage TEXT NOT NULL DEFAULT '',
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    interval INTEGER NOT NULL,
    last_update INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    CHECK (last_update >= 0),
    CHECK (interval > 0)
) STRICT
    """,
    "CREATE INDEX feed_up_idx ON feed (last_update)",
    """
CREATE TABLE item (
    id INTEGER PRIMARY KEY,
    feed_id INTEGER NOT NULL,
    url TEXT UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    timestamp INTEGER NOT NULL,
    FOREIGN KEY (feed_id) REFERENCES feed (id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
    CHECK (timestamp >= 0)
) STRICT
    """,
    "CREATE INDEX item_feed_idx ON item (feed_id)",
    "CREATE INDEX item_time_idx ON item (timestamp)",
    """
CREATE TABLE tag (
    id INTEGER PRIMARY KEY,
    parent INTEGER,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT ''
) STRICT
    """,
    "CREATE INDEX tag_parent_idx ON tag (parent)",
    """
CREATE TABLE tag_link (
    id INTEGER PRIMARY KEY,
    tag_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    UNIQUE (tag_id, item_id),
    FOREIGN KEY (tag_id) REFERENCES tag (id)
      ON UPDATE RESTRICT
      ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES item (id)
      ON UPDATE RESTRICT
      ON DELETE CASCADE
) STRICT
    """,
    "CREATE INDEX tag_link_item_idx ON tag_link (item_id)",
    "CREATE INDEX tag_link_tag_idx ON tag_link (tag_id)",
]


class Query(Enum):
    """Query identifies the various operations we perform on the database."""

    FeedAdd = auto()
    FeedGetAll = auto()
    FeedGetByID = auto()
    FeedGetPending = auto()
    FeedSetLastUpdate = auto()
    FeedSetInterval = auto()
    FeedSetActive = auto()
    FeedDelete = auto()

    ItemAdd = auto()
    ItemGetRecent = auto()
    ItemGetByURL = auto()
    ItemSearch = auto()

    TagAdd = auto()
    TagGetAll = auto()
    TagDelete = auto()

    TagLinkAdd = auto()
    TagLinkGetByTag = auto()
    TagLinkGetByItem = auto()
    TagLinkDelete = auto()


qdb: Final[dict[Query, str]] = {
    Query.FeedAdd: """
INSERT INTO feed (url, homepage, name, description, interval)
          VALUES (  ?,        ?,    ?,           ?,        ?)
RETURNING id
    """,
    Query.FeedGetAll: """
SELECT
    id,
    url,
    homepage,
    name,
    description,
    interval,
    last_update,
    active
FROM feed
    """,
    Query.FeedGetByID: """
SELECT
    url,
    homepage,
    name,
    description,
    interval,
    last_update,
    active
FROM feed
WHERE id = ?
    """,
    Query.FeedGetPending: """
SELECT
    id,
    url,
    homepage,
    name,
    description,
    interval,
    last_update,
    active
FROM feed
WHERE last_update + interval < ?
    """,
    Query.FeedSetActive: "UPDATE feed SET active = ? WHERE id = ?",
    Query.FeedSetLastUpdate: "UPDATE feed SET last_update = ? WHERE id = ?",
    Query.FeedSetInterval: "UPDATE feed SET interval = ? WHERE id = ?",
    Query.FeedDelete: "DELETE FROM feed WHERE id = ?",

    Query.ItemAdd: """
INSERT INTO item (feed_id, url, headline, body, timestamp)
          VALUES (      ?,   ?,        ?,    ?,         ?)
RETURNING id
    """,
    Query.ItemGetRecent: """
SELECT
    id,
    feed_id,
    url,
    headline,
    body,
    timestamp
FROM item
ORDER BY timestamp DESC
LIMIT ?
OFFSET ?
    """,
    Query.ItemGetByURL: """
SELECT
    id,
    feed_id,
    headline,
    body,
    timestamp
FROM item
WHERE url = ?
    """,
}


open_lock: Final[Lock] = Lock()


class Database:
    """Database wraps the database connection and the operations we perform on it."""

    __slots__ = [
        "db",
        "log",
        "path",
    ]

    log: logging.Logger
    db: sqlite3.Connection
    path: str

    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            self.path = common.path.db
        else:
            self.path = path

        self.log = common.get_logger("database")
        self.log.debug("Open database at %s", self.path)

        with open_lock:
            exist: Final[bool] = krylib.fexist(self.path)
            self.db = sqlite3.connect(self.path)
            self.db.isolation_level = None

            cur: Final[sqlite3.Cursor] = self.db.cursor()
            cur.execute("PRAGMA foreign_keys = true")
            cur.execute("PRAGMA journal_mode = WAL")

            if not exist:
                self.__create_db()

    def __create_db(self) -> None:
        """Initialize a freshly created database"""
        self.log.debug("Initialize fresh database at %s", self.path)
        with self.db:
            for query in qinit:
                try:
                    cur: sqlite3.Cursor = self.db.cursor()
                    cur.execute(query)
                except sqlite3.OperationalError as operr:
                    self.log.debug("%s executing init query: %s\n%s\n",
                                   operr.__class__.__name__,
                                   operr,
                                   query)
                    raise
        self.log.debug("Database initialized successfully.")

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()
        self.db = None

    def __enter__(self) -> None:
        self.db.__enter__()

    def __exit__(self, ex_type, ex_val, tb):
        return self.db.__exit__(ex_type, ex_val, tb)

    def feed_add(self, feed: Feed) -> None:
        """Add an RSS Feed to the database."""
        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedAdd], (feed.url,
                                         feed.homepage,
                                         feed.name,
                                         feed.description,
                                         feed.interval))
        row = cur.fetchone()
        feed.fid = row[0]

    def feed_get_all(self) -> list[Feed]:
        """Load all Feeds from the database."""
        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedGetAll])

        feeds: list[Feed] = []

        for row in cur:
            stamp: Optional[datetime] = datetime.fromtimestamp(row[6]) \
                if row[6] is not None \
                else None
            f: Feed = Feed(
                fid=row[0],
                url=row[1],
                homepage=row[2],
                name=row[3],
                description=row[4],
                interval=row[5],
                last_update=stamp,
                active=row[7],
            )
            feeds.append(f)

        return feeds

    def feed_get_by_id(self, feed_id: int) -> Optional[Feed]:
        """Look up a Feed by its ID."""
        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedGetByID], (feed_id, ))

        row = cur.fetchone()
        if row is None:
            return None

        feed: Feed = Feed(
            fid=feed_id,
            url=row[0],
            homepage=row[1],
            name=row[2],
            description=row[3],
            interval=row[4],
            last_update=datetime.fromtimestamp(row[5]),
            active=row[6],
        )

        return feed

    def feed_get_pending(self) -> list[Feed]:
        """Load all Feeds that are due for an update."""
        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedGetPending])

        feeds: list[Feed] = []

        for row in cur:
            f = Feed(
                fid=row[0],
                url=row[1],
                homepage=row[2],
                name=row[3],
                description=row[4],
                interval=row[5],
                last_update=datetime.fromtimestamp(row[6]),
                active=row[7],
            )
            feeds.append(f)

        return feeds

    def feed_set_active(self, feed: Feed, active: bool = True) -> None:
        """Set or clear a Feed's active flag."""
        assert feed.fid > 0

        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedSetActive], (active, feed.fid))
        feed.active = active

    def feed_set_last_update(self, feed: Feed, timestamp: datetime) -> None:
        """Update a Feed's last_update timestamp."""
        if feed.last_update is not None:
            assert timestamp > feed.last_update

        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedSetLastUpdate], (timestamp.timestamp(), feed.fid))
        feed.last_update = timestamp

    def feed_set_interval(self, feed: Feed, interval: int) -> None:
        """Set a Feed's refresh interval."""
        if interval <= 0:
            raise ValueError(f"Invalid interval: {interval} (must be > 0)")

        cur = self.db.cursor()
        cur.execute(qdb[Query.FeedSetInterval], (interval, feed.fid))
        feed.interval = interval

    def item_add(self, item: Item) -> None:
        """Add an Item to the database."""
        cur = self.db.cursor()
        cur.execute(qdb[Query.ItemAdd],
                    (item.feed_id,
                     item.url,
                     item.headline,
                     item.body,
                     math.floor(item.timestamp.timestamp())))
        row = cur.fetchone()
        item.item_id = row[0]

    def item_get_recent(self, limit: int = 100, offset: int = 0) -> list[Item]:
        """
        Fetch the <limit> most recent Items from the database. Skip the first <offset> Items.

        Pass limit = -1 to get all Items (use with great care!)
        """
        cur = self.db.cursor()
        cur.execute(qdb[Query.ItemGetRecent], (limit, offset))

        items: list[Item] = []

        for row in cur:
            item = Item(
                item_id=row[0],
                feed_id=row[1],
                url=row[2],
                headline=row[3],
                body=row[4],
                timestamp=datetime.fromtimestamp(row[5]),
            )
            items.append(item)

        return items

    def item_get_by_url(self, url: str) -> Optional[Item]:
        """Load an Item by its URL"""

    def item_search(self, _query: str) -> list[Item]:
        """Search the Items in the database for <query>."""
        return []

# Local Variables: #
# python-indent: 4 #
# End: #
