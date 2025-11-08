#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-08 14:34:31 krylon>
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
import pickle
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from threading import RLock
from typing import Final, Optional, Union

import lmdb
from krylib import Singleton

from headlines import common
from headlines.common import HeadlineError


class CacheError(HeadlineError):
    """Exception class to indicate errors in the caching layer"""


class TxError(CacheError):
    """TxError indicates an error related to transaction-handling."""


@dataclass(kw_only=True, slots=True)
class CacheItem:
    """CacheItem is a piece of data we want to cache, plus an expiration timestamp."""

    item: Union[str, dict[str, float]]
    expires: datetime

    @property
    def valid(self) -> bool:
        """Return True if the Item's expiration time has not passed, yet."""
        return self.expires > datetime.now()


class DBType(Enum):
    """DBType represents what kind of data we want to cache."""

    Stemmer = auto()
    Scrub = auto()
    Advice = auto()
    Rating = auto()
    Language = auto()

    @property
    def string(self) -> str:
        """Return the lowercase name of the DBType constant."""
        return self.name.lower()


@dataclass(kw_only=True, slots=True)
class Tx:
    """Tx wraps a database transaction."""

    log: logging.Logger
    tx: lmdb.Transaction
    rw: bool
    ttl: timedelta

    def __getitem__(self, key: str) -> Optional[Union[str, dict[str, float]]]:
        val = self.tx.get(key.encode())
        if val is None:
            return None

        item = pickle.loads(val)
        if item.valid:
            return item.item
        if self.rw:
            self.tx.delete(key)

        return None

    def __setitem__(self, key: str, val: Union[str, dict[str, float]]) -> None:
        if not self.rw:
            raise TxError("Cannot change the database in a readonly transaction!")

        item = CacheItem(item=val, expires=datetime.now()+self.ttl)
        raw = pickle.dumps(item)

        self.tx.put(key.encode(), raw, overwrite=True)

    def __delitem__(self, key) -> None:
        if not self.rw:
            raise TxError("Cannot change the database in a readonly transaction!")

        self.tx.delete(key.encode())

    def __contains__(self, key) -> bool:
        val = self.tx.get(key.encode())
        if val is None:
            return False

        item = pickle.loads(val)
        if self.rw and not item.valid:
            self.tx.delete(key)
        return item.valid


@dataclass(kw_only=True, slots=True)
class CacheDB:
    """CacheDB wraps a database with in the LMDB environment."""

    name: DBType
    env: lmdb.Environment
    db: 'lmdb._Database' = field(default=None)
    log: logging.Logger = field(init=False)
    ttl: timedelta = field(default_factory=lambda: timedelta(seconds=7200))

    def __post_init__(self) -> None:
        self.log = common.get_logger(f"cache.{self.name.string}")
        self.log.debug("%s cache coming right up.", self.name)
        if self.db is None:
            self.log.info("No database instance was provided, opening one now.")
            self.db = self.env.open_db(self.name.string)

    @contextmanager
    def tx(self, rw: bool = False):
        """Perform a database transaction. Unless rw is True, no changes are permitted."""
        tx: lmdb.Transaction = self.env.begin(write=rw, db=self.db)
        try:
            yield Tx(log=self.log, tx=tx, rw=rw, ttl=self.ttl)
        except Exception as err:  # noqa: F841 # pylint: disable-msg=W0718
            cname: Final[str] = err.__class__.__name__
            self.log.error("Abort transaction due to %s: %s",
                           cname,
                           err)
            tx.abort()
        else:
            tx.commit()

    def purge(self, complete: bool = False) -> None:
        """Remove stale entries from the Cache. If <complete> is True, remove ALL entries."""
        self.log.debug("Purge %s cache", self.name)
        with self.env.begin(write=True, db=self.db) as tx:
            cur: lmdb.Cursor = tx.cursor()

            for key, val in cur:
                try:
                    item: CacheItem = pickle.loads(val)
                except pickle.PickleError as err:
                    self.log.error("PickleError trying to de-serialize cache item %s: %s",
                                   key,
                                   err)
                else:
                    self.log.debug("Check if Item %s has expired",
                                   item.item)
                    if complete or not item.valid:
                        cur.delete()


class Cache(metaclass=Singleton):
    """Cache provides persistent caching within the application."""

    __slots__ = [
        "log",
        "lock",
        "env",
        "path",
    ]

    log: logging.Logger
    env: lmdb.Environment
    path: str

    def __init__(self, cache_root: str = "") -> None:
        self.log = common.get_logger("cache")
        if cache_root == "":
            cache_root = str(common.path.cache.joinpath("lmdb"))
        self.path = cache_root
        self.log.debug("Open Cache environment in %s", cache_root)
        self.lock = RLock()
        self.env = lmdb.Environment(cache_root,
                                    subdir=True,
                                    map_size=(1 << 40),  # 1 TiB
                                    metasync=False,
                                    create=True,
                                    max_dbs=len(DBType)+2,
                                    )

    def get_db(self, name: DBType, ttl: Union[int, float, timedelta] = 7200) -> CacheDB:
        """Return the specified database."""
        # LMDB caches databases already, so we don't need to duplicate that.
        self.log.debug("Open %s cache.", name)
        ettl: timedelta = ttl if isinstance(ttl, timedelta) else timedelta(seconds=ttl)
        db: 'lmdb._Database' = self.env.open_db(name.string.encode())
        cdb = CacheDB(name=name, env=self.env, db=db, ttl=ettl)
        return cdb

# Local Variables: #
# python-indent: 4 #
# End: #
