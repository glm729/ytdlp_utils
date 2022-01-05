#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import time

from message_handler import MessageHandler
from subprocess_runner import SubprocessRunner
from text_link_parser import TextLinkParser


# Class definition
# -----------------------------------------------------------------------------


class BatchHandler:

    def __init__(self, file_path: str):
        self._path = file_path

    # ---- Public methods

    def run(self):
        """Run all video downloads

        Records time to complete operations for more interesting messages.
        Loops over all video IDs, initialises a subprocess runner, and runs the
        download.
        """
        self._init_message_handler()
        if not self._read_video_links(self._path):
            self._end_message_handler()
            return
        time_start = time.time()
        for v in self.video_data:
            SubprocessRunner(**v).run()
        time_end = time.time() - time_start
        self._message(f"Video{self._s} downloaded in {time_end:.1f}s", "ok")
        self._end_message_handler()

    # ---- Private methods

    def _end_message_handler(self) -> None:
        """End the instance message handler"""
        self._message_handler.end()

    def _init_message_handler(self) -> None:
        """Initialise the instance message handler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text: str, form: str) -> None:
        """Print a message to the terminal, via the message handler instance

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _read_video_links(self, path: str) -> bool:
        """Read the video links text file and store the data

        @param path Path to the video links text file.
        """
        data = TextLinkParser(path=path)
        if (l := len(v := data.video_ids)) > 0:
            self._s = '' if l == 1 else "s"
            self._message(f"Found {l} video ID{self._s}", "ok")
            self._store_video_data(v)
            return True
        self._message("No video IDs found", "warn")
        return False

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
