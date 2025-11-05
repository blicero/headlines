#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-05 16:11:49 krylon>
#
# /data/code/python/headlines/scrub.py
# created on 17. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.scrub

(c) 2025 Benjamin Walkenhorst

This module implements the sanitizing of Item bodies, and the caching of the results.
"""


import logging
from threading import Lock
from typing import Final

from bs4 import BeautifulSoup
from krylib import Singleton

from headlines import common
from headlines.cache import Cache, CacheDB, DBType

# TODO Caching!!!


class Scrubber(metaclass=Singleton):
    """Scrubber sanitizes the HTML of RSS Items:

    - Remove Javascript
    - Change links to open in new tabs/windows
    """

    __slots__ = [
        "log",
        "lock",
        "_cache",
    ]

    log: logging.Logger
    lock: Lock
    _cache: CacheDB

    def __init__(self) -> None:
        self.log = common.get_logger("scrubber")
        self.lock = Lock()
        self._cache = Cache().get_db(DBType.Scrub)

    def scrub_html(self, content: str, _key: int = 0) -> str:
        """Attempt to sanitize the given HTML content."""
        key = str(_key)
        with self._cache.tx(True) as tx:
            if key in tx:
                return tx[key]

            soup = BeautifulSoup(content, "html.parser")
            for link in soup.find_all("a"):
                link.attrs["target"] = "_blank"

            scripts = soup.find_all("script")
            for s in scripts:
                s.decompose()

            proc: Final[str] = str(soup)
            tx[key] = proc

            return proc

# Local Variables: #
# python-indent: 4 #
# End: #
