#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import re
import threading
import time


# Class definition
# -----------------------------------------------------------------------------


class PlaylistHandler:

    _error_message = {
        104: ''.join((
            "WARNING: [youtube] Unable to download webpage: ",
            "<urlopen error [Errno 104] Connection reset by peer>")),
        110: ''.join((
            "ERROR: unable to download video data: ",
            "<urlopen error [Errno 110] Connection timed out>"))
    }

    _playlist_index = 0

    _rex = {}

    _ytdlp_options = {
        "format": "/".join((
            "298+bestaudio",
            "136+bestaudio",
            "22",
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "output": "/".join((
            "%(uploader)s/%(playlist_title)s",
            "%(playlist_index)s__%(title)s.%(ext)s"))
    }

    def __init__(self, playlist_id: str):
        self.playlist_id = playlist_id

    # ---- Public methods

    def run(self):
        pass

    # ---- Private methods

    def _fun_thread_stderr(self, stderr):
        while (l := stderr.readline()):
            line = l.decode("utf-8").strip()

    def _fun_thread_stdout(self, stdout):
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()

    def _generate_command(self, index_start: int):
        return (
            "yt-dlp",
            "--force-ipv4",
            "--geo-bypass",
            "--newline",
            "--format",
            self._ytdlp_options.get("format"),
            "--output",
            self._ytdlp_options.get("output"),
            "--playlist-start",
            str(index_start),
            self.playlist_id)


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    pass
