#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Time-stamp: <2025-11-15 16:13:06 krylon>
#
# /data/code/python/headlines/main.py
# created on 11. 10. 2025
# (c) 2025 Benjamin Walkenhorst
#
# This file is part of the PyKuang network scanner. It is distributed under the
# terms of the GNU General Public License 3. See the file LICENSE for details
# or find a copy online at https://www.gnu.org/licenses/gpl-3.0

"""
headlines.main

(c) 2025 Benjamin Walkenhorst
"""


import argparse
import pathlib
import signal
from threading import Thread

from headlines import common
from headlines.engine import Engine
from headlines.web import WebUI


def main() -> None:
    """Run the headlines application."""
    argp: argparse.ArgumentParser = argparse.ArgumentParser()
    argp.add_argument("-e", "--engine",
                      action="store_true",
                      help="Run the RSS fetcher engine")
    argp.add_argument("-w", "--web",
                      action="store_true",
                      help="Run the web server")
    argp.add_argument("-a", "--address",
                      default="localhost",
                      help="The IP address(es) or hostname to listen on")
    argp.add_argument("-p", "--port",
                      type=int,
                      default=4107,
                      help="The port for the web interface to listen on")
    argp.add_argument("-b", "--basedir",
                      type=pathlib.Path,
                      default=common.path.base(),
                      help="The directory to store application-specific files in")

    args = argp.parse_args()

    common.set_basedir(args.basedir)
    eng: Engine = Engine(10)

    threads: list[Thread] = []

    if args.engine:
        t = Thread(target=eng.start, daemon=False)
        t.start()
        threads.append(t)

    # I need to figure out how to stop the server in an orderly fashion.
    if args.web:
        srv = WebUI("", args.address, args.port)
        t = Thread(target=srv.run, daemon=True)
        t.start()
        # threads.append(t)

    # ...

    if len(threads) == 0:
        # Looks like we have nothing to do! \o/
        return

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("Quitting now, bye!")

    eng.active = False

    for t in threads:
        t.join()

    print("So long, and thanks for all the fish.")


if __name__ == '__main__':
    main()


# Local Variables: #
# python-indent: 4 #
# End: #
