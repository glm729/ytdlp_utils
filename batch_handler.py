#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import time

from _modules.message import Message
from text_link_parser import TextLinkParser
from subprocess_runner import SubprocessRunner


# Class definition
# -----------------------------------------------------------------------------


class BatchHandler:

    def __init__(self):
        pass

    # ---- Public methods

    def read_video_links(self, path: str) -> None:
        """Read the video links text file and store the data

        @param path Path to the video links text file.
        """
        data = TextLinkParser(path=path)
        if (l := len(v := data.video_ids)) > 0:
            self._s = '' if l == 1 else "s"
            self._message(f"Found {l} video ID{self._s}", "ok")
            self._store_video_data(v)
            return
        raise RuntimeError("No video IDs found")

    def run(self):
        """Run all video downloads

        Records time to complete operations for more interesting messages.
        Loops over all video IDs, initialises a subprocess runner, and runs the
        download.
        """
        time_start = time.time()
        for v in self.video_data:
            SubprocessRunner(**v).run()
        time_end = time.time() - time_start
        self._message(f"Video{self._s} downloaded in {time_end:.1f}s", "ok")

    # ---- Private methods

    def _message(self, t: str, f: str) -> None:
        """Print a message to the terminal

        @param t Message text.
        @param f Message form.
        """
        Message(t, form=f).print()

    def _store_video_data(self, video_ids) -> None:
        """Store the video ID data in the instance

        Provides colouring for the video ID prefix.

        @param video_ids Array of video IDs to store.
        """
        colour_index = 30
        self.video_data = []
        for vid in video_ids:
            self.video_data.append({
                "video_id": vid,
                "colour_index": colour_index
            })
            if colour_index == 37:
                colour_index -= 7
                continue
            colour_index += 1
