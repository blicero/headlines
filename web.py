#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-10-16 19:16:21 krylon>
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


import json
import logging
import os
import pathlib
import re
import socket
from datetime import datetime
from threading import Lock
from typing import Any, Final, Optional, Union

import bottle
from bottle import request, response, route, run
from jinja2 import Environment, FileSystemLoader

from headlines import common
from headlines.classy import Karl
from headlines.database import Database, DatabaseError
from headlines.model import Feed, Item, Rating

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

    __slots__ = [
        "log",
        "lock",
        "root",
        "tmpl_root",
        "env",
        "host",
        "port",
        "karl",
    ]

    log: logging.Logger
    lock: Lock
    root: pathlib.Path
    tmpl_root: pathlib.Path
    env: Environment
    host: str
    port: int
    karl: Karl

    def __init__(self, root: Union[str, pathlib.Path] = "") -> None:
        self.log = common.get_logger("WebUI")
        self.lock = Lock()

        self.host = "localhost"
        self.port = 4107

        match root:
            case "":
                self.root = pathlib.Path("./web")
            case str(x):
                self.root = pathlib.Path(x)
            case _ if isinstance(root, pathlib.Path):
                self.root = root
            case _:
                raise TypeError("Invalid type for root (must be str or pathlib.Path)")

        self.karl = Karl()
        if not self.karl.has_cache():
            db: Database = Database()
            items: list[Item] = db.item_get_rated()
            self.karl.train_bulk(items)

        self.tmpl_root = self.root.joinpath("templates")
        self.env = Environment(loader=FileSystemLoader(str(self.tmpl_root)))
        self.env.globals = {
            "dbg": common.Debug,
            "app_string": f"{common.AppName} {common.AppVersion}",
            "hostname": socket.gethostname(),
        }

        bottle.debug(common.Debug)
        route("/main", callback=self._handle_main)
        route("/news", callback=self._handle_news)
        route("/news/<cnt:int>/<offset:int>", callback=self._handle_news)

        route("/ajax/beacon", callback=self._handle_beacon)
        route("/ajax/item_rate/<item_id:int>/<score:int>",
              method="POST",
              callback=self._handle_rate_item)
        route("/ajax/item_unrate/<item_id:int>",
              method="POST",
              callback=self._handle_unrate_item)
        route("/ajax/subscribe",
              method="POST",
              callback=self._handle_subscribe)

        route("/static/<path>", callback=self._handle_static)
        route("/favicon.ico", callback=self._handle_favicon)

    def _tmpl_vars(self) -> dict:
        """Return a dict with a few default variables filled in already."""
        default: dict = {
            "now": datetime.now().strftime(common.TimeFmt),
            "year": datetime.now().year,
            "time_fmt": common.TimeFmt,
        }

        return default

    def run(self) -> None:
        """Run the web server."""
        run(host=self.host, port=self.port, debug=common.Debug)

    def _handle_main(self) -> str:
        """Presents the landing page."""
        db: Database = Database()
        try:
            feeds: list[Feed] = db.feed_get_all()
            response.set_header("Cache-Control", "no-store, max-age=0")
            tmpl = self.env.get_template("main.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["title"] = f"{common.AppName} {common.AppVersion} - Main"
            tmpl_vars["year"] = datetime.now().year
            tmpl_vars["feeds"] = feeds
            # tmpl_vars["hosts"] = db.host_get_all()
            return tmpl.render(tmpl_vars)
        finally:
            db.close()

    def _handle_news(self, cnt: int = 100, offset: int = 0) -> Union[str, bytes]:
        """Present news Items."""
        db: Database = Database()
        try:
            items: list[Item] = db.item_get_recent(cnt, offset)
            feeds: list[Feed] = db.feed_get_all()

            for item in items:
                if item.is_rated:
                    continue

                rating: Rating = self.karl.classify(item)
                item.cache_rating(rating, 0.75)

            response.set_header("Cache-Control", "no-store, max-age=0")
            tmpl = self.env.get_template("news.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["title"] = f"{common.AppName} {common.AppVersion} - News"
            tmpl_vars["year"] = datetime.now().year
            tmpl_vars["feeds"] = {f.fid: f for f in feeds}
            tmpl_vars["items"] = items

            return tmpl.render(tmpl_vars)
        finally:
            db.close()

    # AJAX Handlers

    def _handle_beacon(self) -> str:
        """Handle the AJAX call for the beacon."""
        jdata: dict[str, Any] = {
            "Status": True,
            "Message": common.AppName,
            "Timestamp": datetime.now().strftime(common.TimeFmt),
            "Hostname": socket.gethostname(),
        }

        response.set_header("Content-Type", "application/json")
        response.set_header("Cache-Control", "no-store, max-age=0")

        return json.dumps(jdata)

    def _handle_subscribe(self) -> Union[str, bytes]:
        """Handle an attempt to subscribe to an RSS feed."""
        feed: Feed = Feed(
            url=request.forms["url"],
            homepage=request.forms["homepage"],
            name=request.forms["title"],
            interval=request.forms["interval"],
        )

        self.log.debug("Adding Feed %s (%s - %s)",
                       feed.name,
                       feed.url,
                       feed.homepage)
        db: Database = Database()
        res: dict = {"timestamp": datetime.now().strftime(common.TimeFmt)}

        try:
            with db:
                db.feed_add(feed)
                if feed.fid != 0:
                    res["status"] = True
                    res["message"] = "ACK"
                else:
                    res["status"] = False
                    res["message"] = "Unknown error"
        except DatabaseError as err:
            cname: Final[str] = err.__class__.__name__
            res["status"] = False
            res["message"] = f"{cname} trying to add Feed {feed.name}: {err}"
            self.log.error(res["message"])
        finally:
            db.close()

        body = json.dumps(res)
        response.set_header("Content-Type", "application/json")
        response.set_header("Cache-Control", "no-store, max-age=0")
        return body

    def _handle_rate_item(self, item_id: int, score: int) -> Union[str, bytes]:
        """Store an Item's Rating in the database."""
        #  self.log.debug("Handle rating Item %d with a %d", item_id, score)
        db: Database = Database()
        try:
            item: Optional[Item] = db.item_get_by_id(item_id)
            res: dict = {}

            if item is None:
                res["status"] = False
                res["message"] = f"Item {item_id} was not found in database"
                res["timestamp"] = datetime.now().strftime(common.TimeFmt)
                self.log.error(res["message"])
            else:
                rating: Final[Rating] = Rating(score)
                with db:
                    db.item_rate(item, rating)

                    res = {
                        "status": True,
                        "message": "ACK",
                        "timestamp": datetime.now().strftime(common.TimeFmt),
                    }
                self.karl.learn(item, rating)
            body = json.dumps(res)
            response.set_header("Content-Type", "application/json")
            response.set_header("Cache-Control", "no-store, max-age=0")
            return body
        finally:
            db.close()

    def _handle_unrate_item(self, item_id: int) -> Union[str, bytes]:
        """Remove an Item's rating."""
        db: Database = Database()
        try:
            item: Optional[Item] = db.item_get_by_id(item_id)
            res: dict = {}

            if item is None:
                res = {
                    "status": False,
                    "message": f"Item {item_id} was not found in database",
                    "timestamp": datetime.now().strftime(common.TimeFmt),
                }
            else:
                with db:
                    db.item_rate(item, Rating.Unrated)
                self.karl.learn(item, Rating.Unrated)
                res = {
                    "status": True,
                    "message": "ACK",
                    "timestamp": datetime.now().strftime(common.TimeFmt),
                    "content": f"""
              <button type="button"
                      class="btn btn-primary"
                      onclick="rate_item({item.item_id}, 1);">
                      Interesting
              </button>
              <button type="button"
                      class="btn btn-secondary"
                      onclick="rate_item({item.item_id}, 0);">
                      Boring
              </button>
                    """,
                }

            body = json.dumps(res)
            response.set_header("Content-Type", "application/json")
            response.set_header("Cache-Control", "no-store, max-age=0")
            return body
        finally:
            db.close()

    # Static files

    def _handle_favicon(self) -> bytes:
        """Handle the request for the favicon."""
        path: Final[str] = os.path.join(self.root, "static", "favicon.ico")
        with open(path, "rb") as fh:
            response.set_header("Content-Type", "image/vnd.microsoft.icon")
            response.set_header("Cache-Control",
                                "no-store, max-age=0" if common.Debug else "max-age=7200")
            return fh.read()

    def _handle_static(self, path) -> bytes:
        """Return one of the static files."""
        # TODO Determine MIME type?
        #      Set caching header?
        mtype = find_mime_type(path)
        response.set_header("Content-Type", mtype)
        response.set_header("Cache-Control",
                            "no-store, max-age=0" if common.Debug else "max-age=7200")

        full_path = os.path.join(self.root, "static", path)
        if not os.path.isfile(full_path):
            self.log.error("Static file %s was not found", path)
            response.status = 404
            return bytes()
        with open(full_path, "rb") as fh:
            return fh.read()


if __name__ == '__main__':
    ui = WebUI()
    ui.run()

# Local Variables: #
# python-indent: 4 #
# End: #
