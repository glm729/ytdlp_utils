#!/usr/bin/env python3.8


# Class definition
# -----------------------------------------------------------------------------


class StatusLine:

    def __init__(self, main: str, prefix: str, suffix: str, pw: int):
        self.m = main
        self.p = prefix
        self.s = suffix
        self._pw = pw
        self.build()

    def build(self):
        """Build the status line text"""
        self.text = "{p} {m}  {s}".format(
            p=self.p,
            m=self.m.ljust(self._pw, " "),
            s=self.s)

    def set_main(self, text: str) -> None:
        """Set the main status line content

        @param text Text to set
        """
        self.m = text
        self.build()

    def set_pad_width(self, pw: int) -> None:
        """Set the pad width for the main content

        @param pw Pad width
        """
        self._pw = pw
        self.build()

    def set_prefix(self, text: str) -> None:
        """Set the prefix for the status line content

        @param text Text to set
        """
        self.p = text
        self.build()

    def set_suffix(self, text: str) -> None:
        """Set the suffix for the status line content

        @param text Text to set
        """
        self.s = text
        self.build()
