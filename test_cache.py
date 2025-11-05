#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-05 15:48:09 krylon>
#
# /data/code/python/headlines/test_cache.py
# created on 05. 11. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.test_cache

(c) 2025 Benjamin Walkenhorst
"""

import os
import shutil
import unittest
from datetime import datetime
from typing import Final, Optional

from headlines import common
from headlines.cache import Cache, CacheDB, DBType

test_dir: Final[str] = os.path.join(
    "/tmp",
    datetime.now().strftime(f"{common.AppName.lower()}_test_database_%Y%m%d_%H%M%S"))


class TestCache(unittest.TestCase):
    """Do some rudimentary tests on the Cache."""

    _cache: Optional[Cache] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Prepare the testing environment."""
        common.set_basedir(test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up afterwards."""
        shutil.rmtree(test_dir, ignore_errors=True)

    @classmethod
    def cache(cls) -> Cache:
        """Return the singleton instance of the cache environment."""
        if cls._cache is None:
            cls._cache = Cache()

        return cls._cache

    def test_01_open_env(self) -> None:
        """Test opening the cache environment."""
        env = self.cache()
        self.assertIsNotNone(env)
        self.assertIsInstance(env, Cache)

    def test_02_open_db(self) -> None:
        """Test opening a database within the cache environment."""
        env = self.cache()
        if env is None:
            self.skipTest("Cache Environment is missing.")

        db = env.get_db(DBType.Stemmer)
        self.assertIsNotNone(db)
        self.assertIsInstance(db, CacheDB)

    def test_03_transaction(self) -> None:
        """Test performing a transaction."""
        env = self.cache()
        if env is None:
            self.skipTest("Cache Environment is missing.")
        db = env.get_db(DBType.Stemmer)
        if db is None:
            self.skipTest("Cache DB is missing.")

        test_data: Final[list[tuple[str, str]]] = [
            ("abobo", "ABOBO"),
            ("bbobo", "BBOBO"),
            ("cbobo", "CBOBO"),
        ]

        with db.tx(True) as tx:
            for low, high in test_data:
                tx[low] = high

        with db.tx() as tx:
            for low, hi in test_data:
                check = tx[low]
                self.assertIsNotNone(check)
                self.assertIsInstance(check, str)
                self.assertEqual(check, hi)

                check = tx[low.upper()]
                self.assertIsNone(check)

# Local Variables: #
# python-indent: 4 #
# End: #
