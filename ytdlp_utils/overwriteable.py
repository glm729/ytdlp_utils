#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import io
import sys


# Class definitions
# -----------------------------------------------------------------------------


class Overwriteable:
    """Handle dynamic, overwriteable display content

    Major credit to tecosaur: https://github.com/tecosaur
    Converted his Julia demo into Python and ran with it a bit.
    """

    def __init__(self, stream=sys.stdout):
        self.buffer = io.StringIO(initial_value="", newline="\n")
        self.content = []
        self.lastlines = 0
        self.stream = stream

    def _build(self) -> None:
        """Build the string buffer contents

        Seeks the start of the string buffer and truncates.  Joins content
        lines by newline.  Prints joined content into the instance string
        buffer.
        """
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)
        output = "\n".join(self.content)
        print(output, end="\n", file=self.buffer)

    def add_line(self, text: str, idx: int = None) -> None:
        """Add a line to the instance content store

        @param text Text to use for the content line
        @param idx Index at which to add or insert the line (optional)
        """
        if idx is None:
            self.content.append(text)
            return
        self.content.insert(idx, text)

    def flush(self) -> None:
        """Flush the current contents to the instance stream

        Builds the content in the instance string buffer.  Clears previous text
        printed to the stream.  Reads the string buffer contents and prints to
        the stream.  Counts lines in the most recent output draw.  Empties the
        string buffer.
        """
        self._build()
        if self.lastlines > 0:
            print(f"\033[{self.lastlines}F\033[J", end="", file=self.stream)
        self.buffer.seek(0, 0)
        output = self.buffer.read()
        print(output, end="", file=self.stream)
        self.lastlines = output.count("\n")
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)

    def replace_line(self, idx: int, text: str) -> None:
        """Replace a line in the instance content store

        @param idx Index at which to replace the line
        @param text Text to use to replace the line
        """
        self.content.pop(idx)
        self.content.insert(idx, text)
