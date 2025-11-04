#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-04 17:50:13 krylon>
#
# /data/code/python/headlines/nlp.py
# created on 04. 11. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.nlp

(c) 2025 Benjamin Walkenhorst
"""

import logging
import re
from dataclasses import dataclass, field
from threading import Lock
from typing import Final

from nltk.stem import SnowballStemmer

from headlines import common

languages: Final[dict[str, str]] = {
    "de": "german",
    "en": "english",
}

tok_pat: Final[re.Pattern] = re.compile(r"\W+")  # ???


@dataclass(slots=True, kw_only=True)
class NLP:
    """NLP wraps the processing of text."""

    log: logging.Logger = field(default_factory=lambda: common.get_logger("nlp"))
    lock: Lock = field(default_factory=Lock)
    stemmer: dict[str, SnowballStemmer] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for cc, lang in languages.items():
            self.stemmer[cc] = SnowballStemmer(lang, True)

    def tokenize(self, raw: str, lng: str = "en") -> list[str]:
        """Break up the Item's text into tokens and perform stemming on them."""
        if lng not in languages:
            self.log.error("Language code %s is not supported. Falling back to English.",
                           lng)
            lng = "en"

        pieces: Final[list[str]] = tok_pat.split(raw.lower())
        tokens: Final[list[str]] = [self.stemmer[lng].stem(x) for x in pieces]

        return tokens

    def preprocess(self, raw: str, lng: str = "en") -> str:
        """Preprocess the text."""
        return " ".join(self.tokenize(raw, lng))

# Local Variables: #
# python-indent: 4 #
# End: #
