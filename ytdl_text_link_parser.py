#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import re

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlTextLinkParser:

    _rex = {
        "normal": re.compile(r"(?<=[\?&]v=)(?P<id>[^\?&]+)"),
        "short": re.compile(r"(?<=youtu\.be\/)(?P<id>[^\?&]+)")
    }

    def __init__(self, path=None):
        if path is not None:
            self.read_file(path)

    # ---- Public methods ----

    def read_file(self, path):
        try:
            with open(path, "r") as fh:
                self.data = self._store_data(fh.read().strip().split())
        except FileNotFoundError as error:
            t = f"File does not exist:  {path}"
            Message(t, form="exit").print()
            raise error
        except (AttributeError, RuntimeError) as error:
            t = "Unexpected input data format"
            Message(t, form="exit").print()
            raise error

    # ---- Private methods ----

    def _store_data(self, data):
        malformed = 0
        video_ids = []
        for value in data:
            if (i := self._check_link(value)) is not None:
                video_ids.append(i)
                continue
            malformed += 1
        if malformed > 0:
            s = '' if malformed == 1 else "s"
            t = f"{malformed} link{s} could not be identified"
            Message(t, form="warn").print()
        if len(video_ids) == 0:
            t = "No links found!"
            Message(t, form="warn").print()
        self.video_ids = video_ids

    def _check_link(self, link):
        if (r := self._rex.get("normal").search(link)) is not None:
            return r.group("id")
        if (r := self._rex.get("short").search(link)) is not None:
            return r.group("id")
        return None
