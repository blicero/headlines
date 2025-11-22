#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-22 21:16:13 krylon>
#
# /data/code/python/headlines/test_model.py
# created on 16. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.test_model

(c) 2025 Benjamin Walkenhorst
"""

import os
import re
import shutil
import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Final, NamedTuple, Optional

from headlines import common
from headlines.model import Blacklist, BlacklistItem, Rating

test_dir: Final[str] = os.path.join(
    "/tmp",
    datetime.now().strftime(f"{common.AppName.lower()}_test_model_%Y%m%d_%H%M%S"))


@dataclass(slots=True)
class RatingTestCase:
    """A test case for Rating."""

    val: str
    res: Rating
    err: bool = False


class TestRating(unittest.TestCase):
    """Test the model classes."""

    def test_rating_from_str(self) -> None:
        """Test creating Rating from string."""
        cases: Final[list[RatingTestCase]] = [
            RatingTestCase("unrated", Rating.Unrated),
            RatingTestCase("Unrated", Rating.Unrated),
            RatingTestCase("UNRATED", Rating.Unrated),
            RatingTestCase("boring", Rating.Boring),
            RatingTestCase("Boring", Rating.Boring),
            RatingTestCase("BORING", Rating.Boring),
            RatingTestCase("interesting", Rating.Interesting),
            RatingTestCase("Interesting", Rating.Interesting),
            RatingTestCase("INTERESTING", Rating.Interesting),
            RatingTestCase("bla", Rating.Unrated, True)
        ]

        for c, i in zip(cases, range(len(cases))):
            with self.subTest(i=i):
                if c.err:
                    with self.assertRaises(ValueError):
                        _ = Rating.from_str(c.val)
                else:
                    r: Rating = Rating.from_str(c.val)
                    self.assertIsNotNone(r)
                    self.assertIsInstance(r, Rating)
                    self.assertEqual(r, c.res)


bl_patterns = (
    "fußball",
    r"\bAI\b",
    r"\bllms?\b",
)


class BlacklistTestCase(NamedTuple):
    """A test case for the Blacklist."""

    txt: str
    res: bool = False


bl_cases: Final[list[BlacklistTestCase]] = [
    BlacklistTestCase("Improve your workflow with AI!", True),
    BlacklistTestCase("Physicists discover a new state of cheese"),
    BlacklistTestCase("Hawaii experiences larger number of whales than usual")
]


class TestBlacklist(unittest.TestCase):
    """Test the Blacklist."""

    _bl: Optional[Blacklist] = None

    @classmethod
    def bl(cls, b: Optional[Blacklist] = None) -> Blacklist:
        """Get or set the Blacklist instance."""
        if b is not None:
            cls._bl = b
        if cls._bl is not None:
            return cls._bl

        raise ValueError("No Blacklist exists.")

    @classmethod
    def setUpClass(cls) -> None:
        """Prepare the testing environment."""
        common.set_basedir(test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up afterwards."""
        shutil.rmtree(test_dir, ignore_errors=True)

    def test_01_create_blacklist(self) -> None:
        """Test creating the Blacklist."""
        items: Final[list[BlacklistItem]] = []
        for pat in bl_patterns:
            item: BlacklistItem = BlacklistItem(item_id=0,
                                                pattern=re.compile(pat, re.I))
            items.append(item)

        bl: Blacklist = Blacklist()
        bl.items = items

        self.bl(bl)

    def test_02_match(self) -> None:
        """Test matching some Items."""
        bl: Blacklist = self.bl()

        for c in bl_cases:
            mt: bool = bl.matches(c.txt)
            self.assertEqual(mt, c.res)


# Local Variables: #
# python-indent: 4 #
# End: #
