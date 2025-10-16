#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-16 18:25:01 krylon>
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
from pathlib import Path
from threading import Lock
from typing import Final, Optional, Union

import krylib

from headlines import common
from headlines.model import Feed, Item, Rating


class DatabaseError(common.HeadlineError):
    """Exception class for database-specific errors."""


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
    time_added INTEGER NOT NULL,
    rating INTEGER NOT NULL DEFAULT -1,
    FOREIGN KEY (feed_id) REFERENCES feed (id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
    CHECK (timestamp >= 0),
    CHECK (rating IN (-1, 0, 1))
) STRICT
    """,
    "CREATE INDEX item_feed_idx ON item (feed_id)",
    "CREATE INDEX item_time_idx ON item (timestamp)",
    "CREATE INDEX item_rated_idx ON item (rating = -1)",
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
    ItemGetRated = auto()
    ItemGetByID = auto()
    ItemGetByURL = auto()
    ItemSearch = auto()
    ItemRate = auto()

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
WHERE COALESCE(last_update, 0) + interval < ?
    """,
    Query.FeedSetActive: "UPDATE feed SET active = ? WHERE id = ?",
    Query.FeedSetLastUpdate: "UPDATE feed SET last_update = ? WHERE id = ?",
    Query.FeedSetInterval: "UPDATE feed SET interval = ? WHERE id = ?",
    Query.FeedDelete: "DELETE FROM feed WHERE id = ?",

    Query.ItemAdd: """
INSERT INTO item (feed_id, url, headline, body, timestamp, time_added)
          VALUES (      ?,   ?,        ?,    ?,         ?,          ?)
RETURNING id
    """,
    Query.ItemGetRecent: """
SELECT
    id,
    feed_id,
    url,
    headline,
    body,
    timestamp,
    time_added,
    rating
FROM item
ORDER BY timestamp DESC
LIMIT ?
OFFSET ?
    """,
    Query.ItemGetRated: """
SELECT
    id,
    feed_id,
    url,
    headline,
    body,
    timestamp,
    time_added,
    rating
FROM item
WHERE rating <> -1
    """,
    Query.ItemGetByID: """
SELECT
    feed_id,
    url,
    headline,
    body,
    timestamp,
    time_added,
    rating
FROM item
WHERE id = ?
    """,
    Query.ItemGetByURL: """
SELECT
    id,
    feed_id,
    headline,
    body,
    timestamp,
    time_added,
    rating
FROM item
WHERE url = ?
    """,
    Query.ItemRate: "UPDATE item SET rating = ? WHERE id = ?",
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
    path: Path

    def __init__(self, path: Optional[Union[Path, str]] = None) -> None:
        if path is None:
            self.path = common.path.db
        else:
            match path:
                case x if isinstance(x, Path):
                    self.path = x
                case x if isinstance(x, str):
                    self.path = Path(x)

        self.log = common.get_logger("database")
        self.log.debug("Open database at %s", self.path)

        with open_lock:
            exist: Final[bool] = krylib.fexist(str(self.path))
            self.db = sqlite3.connect(str(self.path))
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
        # self.db = None
        del self.db

    def __enter__(self) -> None:
        self.db.__enter__()

    def __exit__(self, ex_type, ex_val, tb):
        return self.db.__exit__(ex_type, ex_val, tb)

    def feed_add(self, feed: Feed) -> None:
        """Add an RSS Feed to the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.FeedAdd], (feed.url,
                                             feed.homepage,
                                             feed.name,
                                             feed.description,
                                             feed.interval))
            row = cur.fetchone()
            feed.fid = row[0]
        except sqlite3.Error as err:
            msg: Final[str] = f"Error adding Feed {feed.name} ({feed.url}): {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_get_all(self) -> list[Feed]:
        """Load all Feeds from the database."""
        try:
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
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to load all Feeds: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_get_by_id(self, feed_id: int) -> Optional[Feed]:
        """Look up a Feed by its ID."""
        try:
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
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to load Feed {feed_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_get_pending(self) -> list[Feed]:
        """Load all Feeds that are due for an update."""
        try:
            now = math.floor(datetime.now().timestamp())
            cur = self.db.cursor()
            cur.execute(qdb[Query.FeedGetPending], (now, ))

            feeds: list[Feed] = []

            for row in cur:
                up_stamp: Optional[datetime] = datetime.fromtimestamp(row[6]) \
                    if row[6] is not None else None
                f = Feed(
                    fid=row[0],
                    url=row[1],
                    homepage=row[2],
                    name=row[3],
                    description=row[4],
                    interval=row[5],
                    last_update=up_stamp,
                    active=row[7],
                )
                feeds.append(f)

            return feeds
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to load pending Feeds: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_set_active(self, feed: Feed, active: bool = True) -> None:
        """Set or clear a Feed's active flag."""
        assert feed.fid > 0

        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.FeedSetActive], (active, feed.fid))
            feed.active = active
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to set Feed {feed.name}'s active flag: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_set_last_update(self, feed: Feed, timestamp: datetime) -> None:
        """Update a Feed's last_update timestamp."""
        if feed.last_update is not None:
            assert timestamp > feed.last_update

        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.FeedSetLastUpdate], (math.floor(timestamp.timestamp()), feed.fid))
            feed.last_update = timestamp
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to set Feed {feed.name}'s Update timestamp: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def feed_set_interval(self, feed: Feed, interval: int) -> None:
        """Set a Feed's refresh interval."""
        if interval <= 0:
            raise ValueError(f"Invalid interval: {interval} (must be > 0)")

        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.FeedSetInterval], (interval, feed.fid))
            feed.interval = interval
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to set Feed {feed.name}'s refresh interval: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_add(self, item: Item) -> None:
        """Add an Item to the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemAdd],
                        (item.feed_id,
                         item.url,
                         item.headline,
                         item.body,
                         math.floor(item.timestamp.timestamp()),
                         math.floor(item.time_added.timestamp())))
            row = cur.fetchone()
            item.item_id = row[0]
        except sqlite3.IntegrityError:
            # This means - almost certainly - the Item already exists
            pass
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg = f"{cname} trying to add Item {item.url}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_get_recent(self, limit: int = 100, offset: int = 0) -> list[Item]:
        """
        Fetch the <limit> most recent Items from the database. Skip the first <offset> Items.

        Pass limit = -1 to get all Items (use with great care!)
        """
        try:
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
                    time_added=datetime.fromtimestamp(row[6]),
                    rating=Rating(row[7]),
                )
                items.append(item)

            return items
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to load recent items (offset {offset} / limit {limit}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_get_rated(self) -> list[Item]:
        """Fetch all rated Items from the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemGetRated])

            items: list[Item] = []

            for row in cur:
                item = Item(
                    item_id=row[0],
                    feed_id=row[1],
                    url=row[2],
                    headline=row[3],
                    body=row[4],
                    timestamp=datetime.fromtimestamp(row[5]),
                    time_added=datetime.fromtimestamp(row[6]),
                    rating=Rating(row[7]),
                )
                items.append(item)

            return items
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to load rated items: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_get_by_url(self, url: str) -> Optional[Item]:
        """Load an Item by its URL"""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemGetByURL], (url, ))

            row = cur.fetchone()
            if row is None:
                self.log.debug("Item %s was not found in database", url)
                return None

            item: Item = Item(
                item_id=row[0],
                feed_id=row[1],
                url=url,
                headline=row[2],
                body=row[3],
                timestamp=datetime.fromtimestamp(row[4]),
                time_added=datetime.fromtimestamp(row[5]),
                rating=Rating(row[6]),
            )

            return item
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to load Item by URL {url}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_get_by_id(self, item_id: int) -> Optional[Item]:
        """Load an Item by its ID"""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemGetByID], (item_id, ))

            row = cur.fetchone()
            if row is None:
                self.log.debug("Item %d was not found in database", item_id)
                return None

            item: Item = Item(
                item_id=item_id,
                feed_id=row[0],
                url=row[1],
                headline=row[2],
                body=row[3],
                timestamp=datetime.fromtimestamp(row[4]),
                time_added=datetime.fromtimestamp(row[5]),
                rating=Rating(row[6]),
            )

            return item
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to load Item by ID {item_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_search(self, _query: str) -> list[Item]:
        """Search the Items in the database for <query>."""
        return []

    def item_rate(self, item: Item, rating: Rating) -> None:
        """Set an Item's Rating in the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemRate], (rating, item.item_id))
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to rate Item {item.item_id} ({item.headline}): {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

# Local Variables: #
# python-indent: 4 #
# End: #
