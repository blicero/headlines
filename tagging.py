#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-26 19:49:22 krylon>
#
# /data/code/python/headlines/tagging.py
# created on 26. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.tagging

(c) 2025 Benjamin Walkenhorst
"""


import logging
import os
from dataclasses import dataclass, field
from threading import Lock
from typing import Final

from simplebayes import SimpleBayes

from headlines import common
from headlines.database import Database

cache_file: Final[str] = "advisor.pickle"


@dataclass(kw_only=True, slots=True)
class Advisor:
    """Advisor suggests Tags for Items."""

    log: logging.Logger = field(default_factory=lambda: common.get_logger("Advisor"))
    lock: Lock = field(default_factory=Lock)
    bayes: SimpleBayes = field(init=False)

    def __post_init(self) -> None:
        full_cache_path = os.path.join(str(common.path.cache), cache_file)
        need_training: Final[bool] = os.isfile(full_cache_path)

        self.bayes = SimpleBayes(cache_path=str(common.path.cache), cache_file=cache_file)

        if need_training:
            self.train()

    def train(self) -> None:
        db: Database = Database()
        try:
            with self.lock:
                self.bayes.flush()
        finally:
            db.close()

# Local Variables: #
# python-indent: 4 #
# End: #
