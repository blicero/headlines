#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-08 14:44:16 krylon>
#
# /data/code/python/headlines/src/headlines/common.py
# created on 30. 09. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.common

(c) 2025 Benjamin Walkenhorst
"""

import logging
import logging.handlers
import os
import pathlib
import sys
from threading import Lock
from typing import Final

AppName: Final[str] = "Headlines"
AppVersion: Final[str] = "0.4.0"
Debug: Final[bool] = True
TimeFmt: Final[str] = "%Y-%m-%d %H:%M:%S"


class HeadlineError(Exception):
    """Base class for application-specific Exceptions."""


class Path:
    """Holds the paths of folders and files used by the application"""

    __base: str

    def __init__(self, root: str = os.path.expanduser(f"~/.{AppName.lower()}.d")) -> None:  # noqa
        self.__base = root

    def base(self, folder: str = "") -> pathlib.Path:
        """
        Return the base directory for application specific files.

        If path is a non-empty string, set the base directory to its value.
        """
        if folder != "":
            self.__base = folder
        return pathlib.Path(self.__base)

    @property
    def window(self) -> pathlib.Path:
        """Return the path of the window state file"""
        return pathlib.Path(os.path.join(self.__base, f"{AppName.lower()}.win"))

    @property
    def state(self) -> pathlib.Path:
        """Return the path of the file to save the state of the game."""
        return pathlib.Path(os.path.join(self.__base, f"{AppName.lower()}.state"))

    @property
    def db(self) -> pathlib.Path:  # pylint: disable-msg=C0103
        """Return the path to the database"""
        return pathlib.Path(os.path.join(self.__base, f"{AppName.lower()}.db"))

    @property
    def log(self) -> pathlib.Path:
        """Return the path to the log file"""
        return pathlib.Path(os.path.join(self.__base, f"{AppName.lower()}.log"))

    @property
    def cache(self) -> pathlib.Path:
        """Return the path of the spool directory."""
        return pathlib.Path(os.path.join(self.__base, "cache"))

    @property
    def config(self) -> pathlib.Path:
        """Return the path of the configuration file"""
        return pathlib.Path(os.path.join(self.__base, f"{AppName.lower()}.toml"))


path: Path = Path(os.path.expanduser(f"~/.{AppName.lower()}.d"))

_lock: Final[Lock] = Lock()  # pylint: disable-msg=C0103
_cache: Final[dict[str, logging.Logger]] = {}  # pylint: disable-msg=C0103


def set_basedir(folder: str) -> None:
    """Set the base dir to the speficied path."""
    path.base(folder)
    init_app()


def init_app() -> None:
    """Initialize the application environment"""
    if not os.path.isdir(path.base()):
        print(f"Create base directory {path.base()}")
        os.mkdir(path.base())
    if not os.path.isdir(path.cache):
        os.mkdir(path.cache)


def get_logger(name: str, terminal: bool = True) -> logging.Logger:
    """Create and return a logger with the given name"""
    with _lock:
        init_app()

        if name in _cache:
            return _cache[name]

        log_format = "%(asctime)s (%(name)-16s / line %(lineno)-4d) " + \
            "- %(levelname)-8s %(message)s"
        max_log_size = 256 * 2**20
        max_log_count = 4

        log_obj = logging.getLogger(name)
        log_obj.setLevel(logging.DEBUG)
        log_file_handler = logging.handlers.RotatingFileHandler(path.log,
                                                                'a',
                                                                max_log_size,
                                                                max_log_count)

        log_fmt = logging.Formatter(log_format)
        log_file_handler.setFormatter(log_fmt)
        log_obj.addHandler(log_file_handler)

        if terminal:
            log_console_handler = logging.StreamHandler(sys.stdout)
            log_console_handler.setFormatter(log_fmt)
            log_console_handler.setLevel(logging.DEBUG)
            log_obj.addHandler(log_console_handler)

        _cache[name] = log_obj
        return log_obj


# Local Variables: #
# python-indent: 4 #
# End: #
