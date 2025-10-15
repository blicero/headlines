#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-15 15:15:55 krylon>
#
# /data/code/python/headlines/tests/test_database.py
# created on 08. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.test_database

(c) 2025 Benjamin Walkenhorst
"""

import os
import shutil
import unittest
from datetime import datetime
from typing import Final, Optional

from headlines import common
from headlines.database import Database
from headlines.model import Feed, Item, Rating

test_dir: Final[str] = os.path.join(
    "/tmp",
    datetime.now().strftime("snoopy_test_database_%Y%m%d_%H%M%S"))


class TestDatabase(unittest.TestCase):
    """Test the Database."""

    conn: Optional[Database] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Prepare the testing environment."""
        common.set_basedir(test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up afterwards."""
        shutil.rmtree(test_dir, ignore_errors=True)

    @classmethod
    def db(cls, db: Optional[Database] = None) -> Database:
        """Set or return the database."""
        if db is not None:
            cls.conn = db
            return db
        if cls.conn is not None:
            return cls.conn

        raise ValueError("No Database connection exists")

    def test_01_db_open(self) -> None:
        """Attempt to open a fresh Database."""
        db: Database = Database()
        self.assertIsNotNone(db)
        self.assertIsInstance(db, Database)  # ???
        self.db(db)

    def test_02_db_add_feed(self) -> None:
        """Attempt to add a Feed."""
        feed: Final[Feed] = Feed(
            url="https://www.example.org/example.html",
            name="Example News Feed",
            homepage="https://www.example.org/",
        )

        db = self.db()
        db.feed_add(feed)
        self.assertGreater(feed.fid, 0)

        feeds: list[Feed] = db.feed_get_all()

        self.assertIsNotNone(feeds)
        self.assertIsInstance(feeds, list)
        self.assertEqual(len(feeds), 1)
        self.assertEqual(feed, feeds[0])

    def test_03_item_add(self) -> None:
        """Attempt to add a few Items."""
        db: Database = self.db()
        feeds: list[Feed] = db.feed_get_all()

        with db:
            for feed in feeds:
                for i in range(100):
                    addr: str = os.path.join(
                        feed.homepage,
                        f"articles/article{i:03d}",
                    )
                    item: Item = Item(
                        feed_id=feed.fid,
                        url=addr,
                        headline=f"Article {i:03d}",
                        body="Bla Bla Bla",
                        timestamp=datetime.now(),
                    )

                    db.item_add(item)
                    self.assertGreater(item.item_id, 0)

    def test_04_item_get_recent(self) -> None:
        """Attempt to load recent Items from the Database."""
        db: Database = self.db()
        items: list[Item] = db.item_get_recent()

        self.assertIsNotNone(items)
        self.assertEqual(len(items), 100)
        for i in items:
            self.assertEqual(i.rating, Rating.Unrated)

    def test_05_item_get_by_id(self) -> None:
        """Attempt to load Items by their IDs."""
        db: Database = self.db()
        items: list[Item] = db.item_get_recent()

        self.assertIsNotNone(items)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 100)

        for i1 in items:
            i2: Optional[Item] = db.item_get_by_id(i1.item_id)
            self.assertIsNotNone(i2)
            assert i2 is not None  # to appease the type checker
            self.assertEqual(i1, i2)

# Local Variables: #
# python-indent: 4 #
# End: #
