#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import re
import yaml

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlYamlLinkParser:

    _rex = {
        "normal": re.compile(r"(?<=[\?&]v=)(?P<id>[^\?&]+)"),
        "short": re.compile(r"(?<=youtu\.be\/)(?P<id>[^\?&]+)")
    }

    def __init__(self, path=None):
        if path is not None:
            self.read_yaml(path)

    # ---- Public methods ----

    def read_yaml(self, path):
        try:
            with open(path, "r") as fh:
                self.data = self._store_data(yaml.safe_load(fh.read()))
        except FileNotFoundError as error:
            t = f"File does not exist:  {path}"
            Message(t, form="exit").print()
            raise error
        except yaml.YAMLError as error:
            t = f"Failed to parse YAML:  {path}"
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
        for (_, value) in data.items():
            if not isinstance(value, list):
                raise RuntimeError("Unexpected input data format")
            for link in value:
                if (i := self._check_link(link)) is not None:
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
