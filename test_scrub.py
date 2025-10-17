#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-17 19:11:51 krylon>
#
# /data/code/python/headlines/test_scrub.py
# created on 17. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.test_scrub

(c) 2025 Benjamin Walkenhorst
"""

import unittest
from typing import Optional

from headlines.scrub import Scrubber


class TestScrubber(unittest.TestCase):
    """Test the HTML sanitizer."""

    _scrubber: Optional[Scrubber] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Preprare the test environment."""

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up after yourself."""

    @classmethod
    def scrubber(cls) -> Scrubber:
        """Get the Scrubber."""
        if cls._scrubber is None:
            cls._scrubber = Scrubber()

        return cls._scrubber

    def test_01_simple(self) -> None:
        """Test the simple cases first."""
        sample = """
        <i>Hello World</i><br/>
        """
        scrubber = self.scrubber()

        output = scrubber.scrub_html(sample)

        self.assertIsNotNone(output)
        self.assertEqual(sample.strip(), output.strip())


# Local Variables: #
# python-indent: 4 #
# End: #
