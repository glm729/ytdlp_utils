#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import os


# Function definitions
# -----------------------------------------------------------------------------


def trim_line_len(max_len: int, text: str):
    """Trim a line to a maximum length

    Trim text and add ellipsis if over the maximum length.  Return unmodified
    text if at or under the maximum length.

    @param max_len Maximum permissible line length
    @param text Text to trim
    """
    if len(text) > max_len:
        return f"{text[:(max_len - 3)]}..."
    return text


# Class definitions
# -----------------------------------------------------------------------------


class StatusLine:

    def __init__(self, main: str, prefix: str, suffix: str, pw: int):
        self.m = main
        self.p = prefix
        self.s = suffix
        self._pw = pw

    def build(self):
        """Build the status line text"""
        mcol = os.get_terminal_size().columns
        self.text = "{p} {m}  ".format(
            p=self.p,
            m=self.m.ljust(self._pw, " "))
        ccol = mcol - len(self.text)
        self.text += trim_line_len(ccol, self.s)

    def set_main(self, text: str) -> None:
        """Set the main status line content

        @param text Text to set
        """
        self.m = text

    def set_pad_width(self, pw: int) -> None:
        """Set the pad width for the main content

        @param pw Pad width
        """
        self._pw = pw

    def set_prefix(self, text: str) -> None:
        """Set the prefix for the status line content

        @param text Text to set
        """
        self.p = text

    def set_suffix(self, text: str) -> None:
        """Set the suffix for the status line content

        @param text Text to set
        """
        self.s = text


class ChannelStatus(StatusLine):

    def __init__(self, idx, main, prefix, suffix, pw):
        super().__init__(main, prefix, suffix, pw)
        self.additional = []
        self.idx = idx

    def build(self):
        """Build the channel status line text

        Handles content length without zero-width control characters.  Handles
        additional line content, assuming an indent of 2.
        """
        mcol = os.get_terminal_size().columns
        mcol_a = mcol - 2
        self.text = "{p} \033[35m{m}\033[m  ".format(
            p=self.p,
            m=self.m.ljust(self._pw, " "))
        ccol = mcol - (len(self.p) + len(self.m) + 3)
        self.text += trim_line_len(ccol, self.s)
        for line in self.additional:
            self.text += f"\n  {trim_line_len(mcol_a, line)}"
