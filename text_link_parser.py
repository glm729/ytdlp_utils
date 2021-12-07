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

    def read_file(self, path) -> None:
        """Attempt to read the video links file

        @param path File path to read and parse.
        """
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

    def _store_data(self, data) -> None:
        """Parse the split text data and store in the instance

        Permits comments for lines starting with a hash or double-slash.
        """
        malformed = 0
        video_ids = []
        for value in data:
            # Ignore empty lines and comments
            if value == '':
                continue
            if value.startswith("#") or value.startswith("//"):
                continue
            # If a link is found by regex search, append
            if (i := self._check_link(value)) is not None:
                video_ids.append(i)
                continue
            # Increment malformed link text
            malformed += 1
        # Warn if at least one malformed link
        if malformed > 0:
            s = '' if malformed == 1 else "s"
            t = f"{malformed} link{s} could not be identified"
            Message(t, form="warn").print()
        # Warn if no links found
        if len(video_ids) == 0:
            t = "No links found!"
            Message(t, form="warn").print()
        self.video_ids = video_ids

    def _check_link(self, link) -> str:
        """Check the given text for a link

        Checks normal format or short format (youtu.be).

        @param link Link text to search within.
        @return Video ID found, or None if nothing found.
        """
        if (r := self._rex.get("normal").search(link)) is not None:
            return r.group("id")
        if (r := self._rex.get("short").search(link)) is not None:
            return r.group("id")
        return None
