#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import re
import yaml

from message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlLinkParser:

    _ = {}

    def __init__(self, path=None):
        if path is not None:
            self.read_yaml(path)

    # ---- Public methods ----

    def read_yaml(self, path):
        try:
            with open(path, "r") as fh:
                self.data = yaml.safe_load(fh.read())
        except FileNotFoundError as error:
            t = f"File does not exist:  {path}"
            Message(t, form="exit").print()
            raise error
        except yaml.YAMLError as error:
            t = f"Failed to parse YAML:  {path}"
            Message(t, form="exit").print()
            raise error

    def parse(self):
        pass

    # ---- Private methods ----
