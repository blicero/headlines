#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-08 16:37:16 krylon>
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
from headlines.model import Feed, Item, Rating, Tag, TagLink


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
    "CREATE UNIQUE INDEX tag_name_idx ON tag (name)",
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
    """
CREATE VIEW IF NOT EXISTS tag_sorted AS
WITH RECURSIVE children(id, name, description, lvl, root, parent, full_name) AS (
    SELECT
        id,
        name,
        description,
        0 AS lvl,
        id AS root,
        COALESCE(parent, 0) AS parent,
        name AS full_name
    FROM tag
    WHERE COALESCE(parent, 0) = 0
    UNION ALL
    SELECT
        tag.id,
        tag.name,
        tag.description,
        lvl + 1 AS lvl,
        children.root,
        tag.parent,
        full_name || '/' || tag.name AS full_name
    FROM tag, children
    WHERE tag.parent = children.id
)

SELECT
        id,
        name,
        description,
        parent,
        lvl,
        full_name
FROM children
ORDER BY full_name
    """,
    """
CREATE TABLE later (
    id INTEGER PRIMARY KEY,
    item_id INTEGER UNIQUE NOT NULL,
    time_marked INTEGER NOT NULL DEFAULT (unixepoch()),
    time_finished INTEGER,
    FOREIGN KEY (item_id) REFERENCES item (id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) STRICT
    """,
    "CREATE INDEX later_item_idx ON later (item_id)",
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
    ItemGetCount = auto()
    ItemSearch = auto()
    ItemRate = auto()

    TagAdd = auto()
    TagGetAll = auto()
    TagGetByID = auto()
    TagGetByName = auto()
    TagGetChildren = auto()
    TagDelete = auto()
    TagSetParent = auto()

    TagLinkAdd = auto()
    TagLinkGetByTag = auto()
    TagLinkGetByItem = auto()
    TagLinkGetTaggedItems = auto()
    TagLinkDelete = auto()
    TagLinkGetItemCount = auto()

    LaterAdd = auto()
    LaterUnmark = auto()
    LaterGetAll = auto()
    LaterGetUnfinished = auto()
    LaterMarkFinished = auto()
    LaterPurge = auto()


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
    Query.ItemGetCount: "SELECT COUNT(id) FROM item",
    Query.ItemRate: "UPDATE item SET rating = ? WHERE id = ?",
    Query.TagAdd: """
INSERT INTO tag (parent, name, description)
         VALUES (?,         ?,           ?)
RETURNING id
    """,
    Query.TagGetAll: """
SELECT
    id,
    parent,
    name,
    description,
    lvl,
    full_name
FROM tag_sorted
    """,
    Query.TagGetByID: """
SELECT
    parent,
    name,
    description
FROM tag
WHERE id = ?
    """,
    Query.TagGetByName: """
SELECT
    id,
    parent,
    description
FROM tag
WHERE name = ?
    """,
    Query.TagGetChildren: """
WITH RECURSIVE children(id, name, lvl, root, parent, full_name) AS (
    SELECT
        id,
        name,
        0 AS lvl,
        id AS root,
        COALESCE(parent, 0) AS parent,
        name AS full_name
    FROM tag WHERE parent = ?
    UNION ALL
    SELECT
        tag.id,
        tag.name,
        lvl + 1 AS lvl,
        children.root,
        tag.parent,
        full_name || '/' || tag.name AS full_name
    FROM tag, children
    WHERE tag.parent = children.id
)

SELECT
        id,
        name,
        parent,
        lvl,
        full_name
FROM children
ORDER BY full_name
    """,
    Query.TagDelete: "DELETE FROM tag WHERE id = ?",
    Query.TagSetParent: "UPDATE tag SET parent = ? WHERE id = ?",
    Query.TagLinkAdd: """
INSERT INTO tag_link (tag_id, item_id)
              VALUES (     ?,       ?)
RETURNING id
    """,
    Query.TagLinkGetByItem: """
SELECT
    t.id,
    t.parent,
    t.name,
    t.description
FROM tag_link l
INNER JOIN tag t ON l.tag_id = t.id
WHERE l.item_id = ?
    """,
    Query.TagLinkGetByTag: """
SELECT
    i.id,
    i.feed_id,
    i.url,
    i.headline,
    i.body,
    i.timestamp,
    i.time_added,
    i.rating
FROM tag_link l
INNER JOIN item i ON l.item_id = i.id
WHERE l.tag_id = ?
    """,
    Query.TagLinkGetTaggedItems: """
WITH idlist AS (SELECT DISTINCT item_id FROM tag_link)

SELECT
    l.item_id,
    i.feed_id,
    i.url,
    i.headline,
    i.body,
    i.timestamp,
    i.time_added,
    i.rating
FROM idlist l
INNER JOIN item i ON l.item_id = i.id
    """,
    Query.TagLinkDelete: "DELETE FROM tag_link WHERE tag_id = ? AND item_id = ?",
    Query.TagLinkGetItemCount: """
WITH links AS (
SELECT
    tag_id,
    COUNT(id) AS cnt
    FROM tag_link
    GROUP BY tag_id
)

SELECT
    t.id,
    t.name,
    t.description,
    t.parent,
    t.lvl,
    t.full_name,
    COALESCE(l.cnt, 0) AS cnt
FROM tag_sorted t
LEFT OUTER JOIN links l ON t.id = l.tag_id
ORDER BY full_name
    """,
    Query.LaterAdd: "INSERT INTO later (item_id) VALUES (?)",
    Query.LaterUnmark: "DELETE FROM later WHERE item_id = ?",
    Query.LaterGetAll: """
SELECT
    id,
    item_id,
    time_marked,
    time_finished
FROM later
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

    def item_get_count(self) -> int:
        """Get the total number of Items in the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.ItemGetCount])
            row = cur.fetchone()
            return row[0]
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to count Items: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def item_search(self, _query: str) -> list[Item]:
        """Search the Items in the database for <query>."""
        self.log.critical("item_search: IMPLEMENTME!!!")
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

    def tag_add(self, tag: Tag) -> None:
        """Add a Tag to the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagAdd], (tag.parent, tag.name, tag.description))

            row = cur.fetchone()
            tag.tag_id = row[0]
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to add Tag {tag.name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_get_all(self) -> list[Tag]:
        """Load all Tags from the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagGetAll])
            tags: list[Tag] = []

            for row in cur:
                t: Tag = Tag(
                    tag_id=row[0],
                    parent=row[1],
                    name=row[2],
                    description=row[3],
                    lvl=row[4],
                    full_name=row[5],
                )
                tags.append(t)
            return tags
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to load all tags: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_get_by_id(self, tag_id: int) -> Optional[Tag]:
        """Load a Tag by its ID."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagGetByID], (tag_id, ))
            row = cur.fetchone()
            tag: Optional[Tag] = None
            if row is not None:
                tag = Tag(
                    tag_id=tag_id,
                    parent=row[0],
                    name=row[1],
                    description=row[2],
                )
            return tag
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to lookup Tag {tag_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_get_by_name(self, name: str) -> Optional[Tag]:
        """Load a Tag by its ID."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagGetByName], (name, ))
            row = cur.fetchone()
            tag: Optional[Tag] = None
            if row is not None:
                tag = Tag(
                    tag_id=row[0],
                    parent=row[1],
                    name=name,
                    description=row[2],
                )
            return tag
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to lookup Tag {name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_get_children(self, root: Tag) -> list[Tag]:
        """Load all tags that are children of <root>"""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagGetChildren], (root.tag_id, ))

            children: list[Tag] = []

            for row in cur:
                t = Tag(tag_id=row[0],
                        name=row[1],
                        parent=row[2])
                children.append(t)

            return children
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = f"{cname} trying to load children of {root.name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_set_parent(self, tag: Tag, parent: Tag) -> None:
        """Update a Tag's parent link."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagSetParent], (parent.tag_id, tag.tag_id))
            tag.parent = parent.tag_id
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to set the parent of Tag {tag.name} to {parent.name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_remove(self, tag: Tag) -> None:
        """Delete a Tag from the database."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagDelete], (tag.tag_id, ))
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to delete Tag {tag.name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_add(self, item: Item, tag: Tag) -> TagLink:
        """Attach <tag> to <item>."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkAdd], (tag.tag_id, item.item_id))

            row = cur.fetchone()
            return TagLink(lid=row[0],
                           tag_id=tag.tag_id,
                           item_id=item.item_id)
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to link Tag {tag.name} to Item {item.item_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_get_by_tag(self, tag: Tag) -> list[Item]:
        """Return all Items with a given Tag."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkGetByTag], (tag.tag_id, ))

            items: list[Item] = []
            for row in cur:
                item: Item = Item(
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
                f"{cname} trying to get Items by Tag {tag.name}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_get_by_item(self, item: Item) -> list[Tag]:
        """Return all Tags linked to <item>."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkGetByItem], (item.item_id, ))

            tags: list[Tag] = []

            for row in cur:
                tag: Tag = Tag(
                    tag_id=row[0],
                    parent=row[1],
                    name=row[2],
                )

                tags.append(tag)
            return tags
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to get Tags for Item {item.item_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_get_tagged_items(self) -> list[Item]:
        """Get a list of all Items that have been tagged."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkGetTaggedItems])

            items: list[Item] = []

            for row in cur:
                item: Item = Item(
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
                f"{cname} trying to get tagged Items: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_delete(self, tag: Tag, item: Item) -> None:
        """Detach <tag> from <item>."""
        try:
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkDelete], (tag.tag_id, item.item_id))
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to detach Tag {tag.name} from Item {item.item_id}: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

    def tag_link_get_item_cnt(self) -> list[Tag]:
        """Get all Tags with the number of linked Items."""
        try:
            # XXX I am not all that certain my solution is even correct, let alone
            #     anywhere near to optimal.
            cur = self.db.cursor()
            cur.execute(qdb[Query.TagLinkGetItemCount])
            tags: list[Tag] = []
            cnt_tbl: dict[int, int] = {}
            children: dict[int, set[int]] = {}
            for row in cur:
                t: Tag = Tag(
                    tag_id=row[0],
                    name=row[1],
                    description=row[2],
                    parent=row[3],
                    lvl=row[4],
                    full_name=row[5],
                    link_cnt=row[6],
                    link_cnt_rec=row[6],
                )

                tags.append(t)

                cnt_tbl[t.tag_id] = t.link_cnt

                children[t.tag_id] = set()
                if t.parent is not None:
                    if t.parent not in children:
                        children[t.parent] = set()
                        children[t.parent].add(t.tag_id)
                    else:
                        children[t.parent].add(t.tag_id)

            for t in tags:
                if t.tag_id in children:
                    for c in children[t.tag_id]:
                        t.link_cnt_rec += cnt_tbl[c]

            return tags
        except sqlite3.Error as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to load Tags with Link counts: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err

# Local Variables: #
# python-indent: 4 #
# End: #
