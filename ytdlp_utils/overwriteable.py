#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import io
import sys


# Class definitions
# -----------------------------------------------------------------------------


class Overwriteable:

    buffer = io.StringIO(initial_value='', newline="\n")
    content = []
    lastlines = 0

    def __init__(self, stream=sys.stdout):
        self.stream = stream


    def _build(self) -> None:
        """Build the buffer content, using the content store"""
        # Clear out the buffer
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)

        # Get the content as a string and print into the buffer
        string = "\n".join(self.content)
        print(string, end="\n", file=self.buffer)


    def add_line(self, text: str, idx: int = None) -> None:
        """Add a line to the content store

        @param text
        @param idx
        """
        if idx is None:
            self.content.append(text)
            return
        self.content.insert(idx, text)


    def flush(self) -> None:
        """Flush the string buffer contents to the instance stream

        Instance stream defaults to `sys.stdout`.
        """
        # Build the buffer content
        self._build()

        # If more than one line, move to top and clear the text below
        if self.lastlines > 0:
            print(f"\033[{self.lastlines}F\033[J", end='', file=self.stream)

        # Seek the start of the string buffer and read
        self.buffer.seek(0, 0)
        string = self.buffer.read()

        # Print string buffer contents to the stream and count newlines
        print(string, end='', file=self.stream)
        self.lastlines = string.count("\n")

        # Seek the start of the string buffer and truncate (clear data)
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)


    # def redraw_at(self, x: int, y: int) -> None:
    #     """Redraw a specific character at a given set of coordinates
    #     @param x
    #     @param y
    #     """
    #     move_x = x  # ... TODO: Check how 0 is handled
    #     move_y = self.lastlines - y


    def redraw_line(self, idx: int) -> None:
        """Redraw a specified line of content

        Will this even work?  Needs testing!

        @param idx Index of the content line to redraw
        """
        move = self.lastlines - idx
        print(f"\033[{move}F\033[2K", end='', file=self.stream)
        print(self.content[idx], end='', file=self.stream)
        # TODO: Reset position to end of content (needs testing)
        # print(f"\033[{move}E", end='', file=self.stream)


    def replace_line(self, idx: int, text: str) -> None:
        """Replace a content line

        @param idx Index of the string to replace
        @param text Text to insert
        """
        self.content.pop(idx)
        self.content.insert(idx, text)
