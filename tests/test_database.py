#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-08 15:26:48 krylon>
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

import common
from database import Database

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

# Local Variables: #
# python-indent: 4 #
# End: #
