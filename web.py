#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-11 20:39:37 krylon>
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
from uuid import uuid4

import bottle
from bottle import request, response, route, run
from jinja2 import Environment, FileSystemLoader

from headlines import common
from headlines.classy import Karl
from headlines.database import Database, DatabaseError
from headlines.model import Feed, Item, Later, Rating, Tag
from headlines.tagging import Advisor

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
        "advisor",
    ]

    log: logging.Logger
    lock: Lock
    root: pathlib.Path
    tmpl_root: pathlib.Path
    env: Environment
    host: str
    port: int
    karl: Karl
    advisor: Advisor

    def __init__(self, root: Union[str, pathlib.Path] = "") -> None:
        self.log = common.get_logger("web")
        self.lock = Lock()

        self.log.info("Web interface is coming up...")

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
        # if not self.karl.has_cache():
        #     db: Database = Database()
        #     items: list[Item] = db.item_get_rated()
        #     self.karl.train_bulk(items)

        self.advisor = Advisor()

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
        route("/tag/all", callback=self._handle_tag_all)
        route("/tag/<tag_id:int>", callback=self._handle_tag_details)
        route("/later", callback=self._handle_later)

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
        route("/ajax/add_tag_link",
              method="POST",
              callback=self._handle_add_tag_link)
        route("/ajax/del_tag_link",
              method="POST",
              callback=self._handle_del_tag_link)
        route("/ajax/items_by_tag/<tag_id:int>",
              method="GET",
              callback=self._handle_items_for_tag)
        route("/ajax/tag/new",
              method="POST",
              callback=self._handle_tag_create)
        route("/ajax/later/add/<item_id:int>",
              method="POST",
              callback=self._handle_later_add)
        route("/ajax/later/done/<item_id:int>",
              method="POST",
              callback=self._handle_later_mark_done)

        route("/static/<path>", callback=self._handle_static)
        route("/favicon.ico", callback=self._handle_favicon)

    def _tmpl_vars(self) -> dict:
        """Return a dict with a few default variables filled in already."""
        default: dict = {
            "now": datetime.now().strftime(common.TimeFmt),
            "year": datetime.now().year,
            "time_fmt": common.TimeFmt,
            "uuid": uuid4,
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
        if cnt <= 0:
            self.log.info("cnt is %d, which is inacceptable. Let's use 100", cnt)
            cnt = 100
        db: Database = Database()
        try:
            items: list[Item] = db.item_get_recent(cnt, offset * cnt)
            feeds: list[Feed] = db.feed_get_all()
            tags: list[Tag] = db.tag_get_all()
            item_tags: dict[int, set[Tag]] = {}
            later: set[Later] = db.item_later_get_all()
            advice: dict[int, list[tuple[Tag, float]]] = {}

            for item in items:
                item_tags[item.item_id] = set(db.tag_link_get_by_item(item))
                if not item.is_rated:
                    rating: Rating = self.karl.classify(item)
                    item.cache_rating(rating, 0.75)

                advice[item.item_id] = self.advisor.advise(
                    item,
                    {t.name for t in item_tags[item.item_id]}
                )

            response.set_header("Cache-Control", "no-store, max-age=0")
            tmpl = self.env.get_template("news.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["title"] = f"{common.AppName} {common.AppVersion} - News"
            tmpl_vars["feeds"] = {f.fid: f for f in feeds}
            tmpl_vars["items"] = items
            tmpl_vars["tags"] = tags
            tmpl_vars["item_tags"] = item_tags
            tmpl_vars["later"] = {lt.item_id: lt for lt in later}
            tmpl_vars["advice"] = advice
            tmpl_vars["page_no"] = offset
            tmpl_vars["page_max"] = db.item_get_count() // cnt
            tmpl_vars["page_size"] = cnt

            return tmpl.render(tmpl_vars)
        finally:
            db.close()

    def _handle_tag_all(self) -> Union[bytes, str]:
        """Present a view of all Tag."""
        db: Final[Database] = Database()
        try:
            tags: list[Tag] = db.tag_link_get_item_cnt()
            tags.sort(key=lambda x: x.full_name)
            response.set_header("Cache-Control", "no-store, max-age=0")
            tmpl = self.env.get_template("tags.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["tags"] = tags
            return tmpl.render(tmpl_vars)
        finally:
            db.close()

    def _handle_tag_details(self, tag_id: int) -> Union[str, bytes]:
        """Display detailed information plus linked Items for a Tag."""
        db: Final[Database] = Database()
        try:
            tmpl_vars = self._tmpl_vars()
            tag: Optional[Tag] = db.tag_get_by_id(tag_id)
            if tag is None:
                response.status_code = 404
                response.set_header("Cache-Control", "no-store, max-age=0")
                tmpl_vars["message"] = f"Tag {tag_id} does not exist"
                tmpl_vars["url"] = request.get_header("Referer")
                tmpl = self.env.get_template("error.jinja")
                return tmpl.render(tmpl_vars)

            items: list[Item] = db.tag_link_get_by_tag(tag)
            item_tags: dict[int, set[Tag]] = {}
            advice: dict[int, list[tuple[Tag, float]]] = {}

            for item in items:
                item_tags[item.item_id] = set(db.tag_link_get_by_item(item))
                if not item.is_rated:
                    rating: Rating = self.karl.classify(item)
                    item.cache_rating(rating, 0.75)

                advice[item.item_id] = self.advisor.advise(item)

            tmpl_vars["tag"] = tag
            tmpl_vars["items"] = items
            tmpl_vars["tags"] = db.tag_get_all()
            tmpl_vars["feeds"] = db.feed_get_all()
            tmpl_vars["advice"] = advice
            tmpl_vars["item_tags"] = item_tags

            # TODO Get and render the template!
            tmpl = self.env.get_template("tag_details.jinja")
            return tmpl.render(tmpl_vars)
        finally:
            db.close()

    def _handle_later(self) -> Union[bytes, str]:
        """Display the read-later list."""
        db: Final[Database] = Database()
        try:
            later: set[Later] = db.item_later_get_all()
            self.log.debug("Rendering %d Items to be read later.",
                           len(later))
            items: dict[int, Item] = {}
            for lt in later:
                item: Optional[Item] = db.item_get_by_id(lt.item_id)
                if item is not None:
                    items[item.item_id] = item
                else:
                    self.log.critical("CANTHAPPEN: Item %d was not found in database", lt.item_id)
            assert len(later) == len(items)
            feeds: list[Feed] = db.feed_get_all()
            response.set_header("Content-Type", "text/html; charset=UTF-8")
            response.set_header("Cache-Control", "no-store, max-age=0")
            tmpl = self.env.get_template("later.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["title"] = f"{common.AppName} {common.AppVersion} - Later"
            tmpl_vars["feeds"] = {f.fid: f for f in feeds}
            tmpl_vars["items"] = items
            tmpl_vars["later"] = later
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

    def _handle_add_tag_link(self) -> Union[str, bytes]:
        """Attach a Tag to an Item"""
        db: Database = Database()
        try:
            # params: Final[str] = ", ".join([f"{x} => {y}" for x, y in request.params.items()])
            # self.log.debug("%s - request.params = %s",
            #                request.fullpath,
            #                params)
            item_id: Final[int] = int(request.params["item_id"])
            tag_id: Final[int] = int(request.params["tag_id"])
            item: Final[Optional[Item]] = db.item_get_by_id(item_id)
            tag: Final[Optional[Tag]] = db.tag_get_by_id(tag_id)
            res = {
                "status": False,
                "timestamp": datetime.now().strftime(common.TimeFmt),
            }

            if item is None:
                res["message"] = f"Item {item_id} was not found in Database"
            elif tag is None:
                res["message"] = f"Tag {tag_id} was not found in Database"
            else:
                with db:
                    db.tag_link_add(item, tag)
                res["message"] = "ACK"
                res["status"] = True
                self.advisor.learn(item, tag)

            body: Final[str] = json.dumps(res)
            response.set_header("Content-Type", "application/json")
            response.set_header("Cache-Control", "no-store, max-age=0")
            return body
        finally:
            db.close()

    def _handle_del_tag_link(self) -> Union[str, bytes]:
        """Remove a Tag from an Item."""
        db: Final[Database] = Database()
        try:
            params: Final[str] = ", ".join([f"{x} => {y}" for x, y in request.params.items()])
            self.log.debug("%s - request.params = %s",
                           request.fullpath,
                           params)
            item_id: Final[int] = int(request.params["item_id"])
            tag_id: Final[int] = int(request.params["tag_id"])
            item: Final[Optional[Item]] = db.item_get_by_id(item_id)
            tag: Final[Optional[Tag]] = db.tag_get_by_id(tag_id)
            res = {
                "status": False,
                "timestamp": datetime.now().strftime(common.TimeFmt),
            }

            if item is None:
                res["message"] = f"Item {item_id} was not found in Database"
            elif tag is None:
                res["message"] = f"Tag {tag_id} was not found in Database"
            else:
                with db:
                    db.tag_link_delete(tag, item)
                res["message"] = "ACK"
                res["status"] = True
                self.advisor.forget(item, tag)

            body: Final[str] = json.dumps(res)
            response.set_header("Content-Type", "application/json")
            response.set_header("Cache-Control", "no-store, max-age=0")
            return body
        finally:
            db.close()

    def _handle_items_for_tag(self, tag_id) -> Union[str, bytes]:
        """Load and render Items for <tag>."""
        db: Database = Database()
        try:
            res: dict = {
                "status": False,
                "timestamp": datetime.now().strftime(common.TimeFmt),
                "message": "",
                "payload": "",
            }

            tags: list[Tag] = []
            tag: Optional[Tag] = db.tag_get_by_id(tag_id)
            items: list[Item] = []
            item_tags: dict[int, set[Tag]] = {}
            advice: dict[int, list[tuple[Tag, float]]] = {}

            if tag is None:
                res["message"] = f"Tag #{tag_id} was not found in database"
            else:
                items = db.tag_link_get_by_tag(tag)
                feeds: list[Feed] = db.feed_get_all()
                tags = db.tag_get_all()
                item_tags = {}
                advice = {}

            for item in items:
                item_tags[item.item_id] = set(db.tag_link_get_by_item(item))
                if not item.is_rated:
                    rating: Rating = self.karl.classify(item)
                    item.cache_rating(rating, 0.75)

                advice[item.item_id] = self.advisor.advise(item)

            response.set_header("Cache-Control", "no-store, max-age=0")
            response.set_header("Content-Type", "application/json")
            tmpl = self.env.get_template("items.jinja")
            tmpl_vars = self._tmpl_vars()
            tmpl_vars["title"] = f"{common.AppName} {common.AppVersion} - News"
            tmpl_vars["year"] = datetime.now().year
            tmpl_vars["feeds"] = {f.fid: f for f in feeds}
            tmpl_vars["items"] = items
            tmpl_vars["tags"] = tags
            tmpl_vars["item_tags"] = item_tags
            tmpl_vars["advice"] = advice
            tmpl_vars["uuid"] = uuid4

            res["status"] = True
            res["message"] = "ACK"
            res["payload"] = tmpl.render(tmpl_vars)

            return json.dumps(res)
        finally:
            db.close()

    def _handle_tag_create(self) -> Union[str, bytes]:
        """Snag it, bag it, tag it."""
        db: Final[Database] = Database()
        res: dict = {
            "status": False,
            "timestamp": datetime.now().strftime(common.TimeFmt),
            "message": "",
        }
        try:
            params: Final[str] = ", ".join([f"{x} => {y}" for x, y in request.params.items()])
            self.log.debug("%s - request.params = %s",
                           request.fullpath,
                           params)

            name: Final[str] = request.params["name"]
            parent: Final[int] = int(request.params["parent"])
            tag: Final[Tag] = Tag(name=name, parent=parent if parent != 0 else None)

            with db:
                db.tag_add(tag)

            res["status"] = True
            res["message"] = "ACK"
        except DatabaseError as err:
            cname: Final[str] = err.__class__.__name__
            res["message"] = f"{cname} trying to add Tag named {name} (parent = {parent}): {err}"
            self.log.error(res["message"])
        finally:
            db.close()

        response.set_header("Cache-Control", "no-store, max-age=0")
        response.set_header("Content-Type", "application/json")
        return json.dumps(res)

    def _handle_later_add(self, item_id: int) -> Union[bytes, str]:
        """Add an Item to the read-later list."""
        res: dict = {
            "status": False,
            "timestamp": datetime.now().strftime(common.TimeFmt),
            "message": "",
            "payload": None,
        }
        db: Final[Database] = Database()
        try:
            with db:
                item: Optional[Item] = db.item_get_by_id(item_id)
                if item is None:
                    res["message"] = f"Item {item_id} does not exist in database"
                else:
                    later: Later = db.item_later_add(item)
                    res["payload"] = later.lid
                    res["status"] = True
        except DatabaseError as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to mark Item {item_id} as read-later: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err
        finally:
            db.close()

        response.set_header("Cache-Control", "no-store, max-age=0")
        response.set_header("Content-Type", "application/json")
        return json.dumps(res)

    def _handle_later_mark_done(self, item_id: int) -> Union[bytes, str]:
        """Mark an Item on the read-later list as done."""
        res: dict = {
            "status": False,
            "timestamp": datetime.now().strftime(common.TimeFmt),
            "message": "",
            "payload": None,
        }
        db: Final[Database] = Database()
        try:
            with db:
                item: Optional[Item] = db.item_get_by_id(item_id)
                if item is None:
                    res["status"] = f"Item {item_id} was not found in database"
                else:
                    db.item_later_mark_done(item)
                    res["status"] = True
        except DatabaseError as err:
            cname: Final[str] = err.__class__.__name__
            msg: Final[str] = \
                f"{cname} trying to mark Item {item_id} as read: {err}"
            self.log.error(msg)
            raise DatabaseError(msg) from err
        finally:
            db.close()

        response.set_header("Cache-Control", "no-store, max-age=0")
        response.set_header("Content-Type", "application/json")
        return json.dumps(res)

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
