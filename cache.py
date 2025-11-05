#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-05 11:13:50 krylon>
#
# /data/code/python/headlines/cache.py
# created on 05. 11. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.cache

(c) 2025 Benjamin Walkenhorst
"""


import logging
from threading import RLock
from typing import Optional

import lmdb
from krylib import Singleton


@Singleton
class Cache:
    """Cache provides persistent caching within the application."""

    __slots__ = [
        "log",
        "lock",
        "env",
        "tx",
    ]

    log: logging.Logger
    Lock: RLock
    env: lmdb.Environment
    tx: Optional[lmdb.Transaction]

    def __init__(self, cache_root: str = "") -> None:
        pass

    def __enter__(self) -> lmdb.Transaction:
        self.lock.Lock()
        self.tx = self.env.begin()
        return self.tx

    def __exit__(self, ex_type, ex_val, tb):
        if ex_val is not None:
            self.tx.abort()
        else:
            self.tx.commit()
        self.tx = None
        self.lock.Unlock()


# Local Variables: #
# python-indent: 4 #
# End: #
