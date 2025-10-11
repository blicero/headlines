#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-11 23:30:38 krylon>
#
# /data/code/python/headlines/web.py
# created on 11. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.web

(c) 2025 Benjamin Walkenhorst
"""


import logging
import pathlib
import re
from threading import Lock
from typing import Final

from jinja2 import Environment

mime_types: Final[dict[str, str]] = {
    ".css":  "text/css",
    ".map":  "application/json",
    ".js":   "text/javascript",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif":  "image/gif",
    ".json": "application/json",
    ".html": "text/html",
}

suffix_pat: Final[re.Pattern] = re.compile("([.][^.]+)$")


def find_mime_type(path: str) -> str:
    """Attempt to determine the MIME type for a file."""
    m = suffix_pat.search(path)
    if m is None:
        return "application/octet-stream"
    suffix = m[1]
    if suffix in mime_types:
        return mime_types[suffix]
    return "application/octet-stream"


class WebUI:
    """Present a shiny face to the casual observer."""

    log: logging.Logger
    tmpl_root: pathlib.Path
    lock: Lock
    env: Environment


# Local Variables: #
# python-indent: 4 #
# End: #
