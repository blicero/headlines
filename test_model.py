#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-16 16:56:31 krylon>
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

import unittest
from dataclasses import dataclass
from typing import Final

from headlines.model import Rating


@dataclass(slots=True)
class RatingTestCase:
    """A test case for Rating."""

    val: str
    res: Rating
    err: bool = False


class TestModel(unittest.TestCase):
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

# Local Variables: #
# python-indent: 4 #
# End: #
