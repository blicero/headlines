#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-09 23:06:55 krylon>
#
# /data/code/python/headlines/src/headlines/engine.py
# created on 30. 09. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.engine

(c) 2025 Benjamin Walkenhorst

Engine implements the downloading and processing of RSS feeds.
"""


import logging
from datetime import timedelta
from queue import SimpleQueue
from threading import Lock
from typing import Union

from headlines import common
from headlines.database import Database


class Engine:
    """Fetcher downloads RSS feeds."""

    __slots__ = [
        "log",
        "db",
        "interval",
        "lock",
        "_active",
        "feedq",
        "itemq",
    ]

    log: logging.Logger
    db: Database
    interval: timedelta
    lock: Lock
    _active: bool
    feedq: SimpleQueue
    itemq: SimpleQueue

    def __init__(self, interval: Union[int, float, timedelta]) -> None:
        self.log = common.get_logger("engine")
        self.db = Database()
        self.lock = Lock()
        self._active = False
        self.feedq = SimpleQueue()
        self.itemq = SimpleQueue()
        match interval:
            case int(x):
                self.interval = timedelta(seconds=x)
            case float(x):
                self.interval = timedelta(seconds=x)
            case x if isinstance(x, timedelta):
                self.interval = x
            case _:
                name = interval.__class__.__name__
                msg = f"Interval must be a number (of seconds) or a timedelta, not a {name}"
                raise ValueError(msg)

        self.log.debug("Engine will check for news every %s seconds.",
                       self.interval.seconds)

    @property
    def active(self) -> bool:
        """Return the Engine's active flag."""
        with self.lock:
            return self._active

    @active.setter
    def active(self, value: bool) -> None:
        """Set the Engine's active flag."""
        with self.lock:
            self._active = value

    def start(self) -> None:
        """Begin to periodically check the datbase for Feeds due for a refresh."""
        self.log.debug("Engine is starting.")
        self.active = True

    def _loop(self) -> None:
        """Perform the outermost main loop."""
        while self.active:
            pass


# Local Variables: #
# python-indent: 4 #
# End: #
