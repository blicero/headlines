#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-05 15:50:13 krylon>
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
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from threading import RLock
from typing import Final, Optional

import lmdb
from krylib import Singleton

from headlines import common
from headlines.common import HeadlineError


class CacheError(HeadlineError):
    """Exception class to indicate errors in the caching layer"""


class TxError(CacheError):
    """TxError indicates an error related to transaction-handling."""


class DBType(Enum):
    """DBType represents what kind of data we want to cache."""

    Stemmer = auto()
    Advice = auto()
    Rating = auto()

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

    def __getitem__(self, key: str) -> Optional[str]:
        val = self.tx.get(key.encode())
        if val is not None:
            return val.decode()
        return None

    def __setitem__(self, key: str, val: str) -> None:
        if not self.rw:
            raise TxError("Cannot change the database in a readonly transaction!")

        self.tx.put(key.encode(), val.encode(), overwrite=True)

    def __delitem__(self, key) -> None:
        if not self.rw:
            raise TxError("Cannot change the database in a readonly transaction!")

        self.tx.delete(key.encode())


@dataclass(kw_only=True, slots=True)
class CacheDB:
    """CacheDB wraps a database with in the LMDB environment."""

    name: DBType
    env: lmdb.Environment
    db: 'lmdb._Database' = field(default=None)
    log: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.log = common.get_logger(f"cache.{self.name.string}")
        if self.db is None:
            self.log.info("No database instance was provided, opening one now.")
            self.db = self.env.open_db(self.name.string)

    @contextmanager
    def tx(self, rw: bool = False):
        """Perform a database transaction. Unless rw is True, no changes are permitted."""
        tx: lmdb.Transaction = self.env.begin(write=rw)
        try:
            yield Tx(log=self.log, tx=tx, rw=rw)
        except Exception as err:  # noqa: F841 # pylint: disable-msg=W0718
            cname: Final[str] = err.__class__.__name__
            self.log.error("Abort transaction due to %s: %s",
                           cname,
                           err)
            tx.abort()
        else:
            tx.commit()


class Cache(metaclass=Singleton):
    """Cache provides persistent caching within the application."""

    __slots__ = [
        "log",
        "lock",
        "env",
        "path",
    ]

    log: logging.Logger
    lock: RLock
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
                                    map_size=(1 << 33),
                                    metasync=False,
                                    create=True,
                                    max_dbs=len(DBType)+2,
                                    )

    def get_db(self, name: DBType) -> CacheDB:
        """Return the specified database."""
        # LMDB caches databases already, so we don't need to duplicate that.
        db: 'lmdb._Database' = self.env.open_db(name.string.encode())
        return CacheDB(name=name, env=self.env, db=db)

    # FIXME I don't think __enter__/__exit__ is the right approach, especially
    #       if I want to support multiple databases.

    # def tx(self, db: str, rw: bool = True) -> lmdb.Transaction:
    #     return self.env.begin(write=rw, db=db)


# Local Variables: #
# python-indent: 4 #
# End: #
