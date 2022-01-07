#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import functools
import json
import time
import yt_dlp

from message_handler import MessageHandler


# Custom logger definition
# -----------------------------------------------------------------------------


class ChannelCheckerLogger:

    def __init__(self, handler):
        self._handler = handler

    def debug(self, message):
        pass

    def error(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass


# Class definition
# -----------------------------------------------------------------------------


class ChannelChecker:

    _ytdlp_defaults = {
        "extract_flat": True
    }

    def __init__(self, file_path: str, n: int = 6):
        self._n = n
        self._path = file_path

    # ---- Public methods

    def run(self) -> None:
        """Public run method

        Initialises and starts message handler.  Ends early if reading and
        parsing the channel data fails.  Instantiates the logger and prepares
        yt_dlp options.  Requests all channel data and processes.  Notifies of
        completion and timing, and ends message handler.
        """
        self._init_message_handler()
        if not self._read_file(self._path):
            self._end_message_handler()
            return
        time_start = time.time()
        self._logger = ChannelCheckerLogger(self)
        ytdlp_options = self._ytdlp_defaults.copy()
        ytdlp_options.update({
            "logger": self._logger,
            "playlistend": self._n,
        })
        with yt_dlp.YoutubeDL(ytdlp_options) as yt:
            func = functools.partial(self._check_channel, yt=yt)
            new_data = list(map(func, self.channel_data))
        self._write_file(self._path, new_data)
        text = "All channels checked in {t:.1f}s"
        self._message(text.format(t=time.time() - time_start), "ok")
        self._end_message_handler()

    # ---- Private methods

    def _check_channel(self, data, yt) -> dict:
        """Extract and check incoming data for the given channel

        @param data Data for the current channel to check.
        @param yt yt_dlp.YoutubeDL instance to use for extracting info.
        """
        self._message(f"{data.get('title')}: Checking recent uploads", "info")
        new_titles = []
        new_videos = []
        new_data = list(map(
            lambda x: { "title": x.get("title"), "uri": x.get("url"), },
            yt.extract_info(data.get("uri"), download=False).get("entries")))
        for new in new_data:
            new_video = True
            for old in data.get("recent_uploads"):
                if new.get("uri") == old.get("uri"):
                    new_video = False
                    if (nt := new.get("title")) != (ot := old.get("title")):
                        new_titles.append((ot, nt))
            if new_video:
                new_videos.append(new.get("title"))
        output = {
            "recent_uploads": new_data,
            "title": data.get("title"),
            "uri": data.get("uri"),
        }
        self._check_new_titles(output, new_titles)
        self._check_new_videos(output, new_videos)
        return output

    def _check_new_titles(self, new_data, new_titles) -> None:
        """Check for and notify of title changes for the given channel

        @param new_data New data for the channel to check.
        @param new_titles List of changed-title 2-tuples for which to notify.
        """
        l = len(new_titles)
        if l == 0:
            return
        s = '' if l == 1 else "s"
        title_changes = map(lambda x: f"\n{' ' * 9}=>  ".join(x), new_titles)
        text = f"{new_data.get('title')}: {l} video title{s} changed:"
        self._message(f"\n{' ' * 7}- ".join((text, *title_changes)), "warn")

    def _check_new_videos(self, new_data, new_videos) -> None:
        """Check for an notify of new videos for the given channel

        @param new_data New data for the channel to check.
        @param new_videos List of new video titles for which to notify.
        """
        l = len(new_videos)
        t = new_data.get("title")
        if l == 0:
            self._message(f"{t}: No new uploads found", "info")
            return
        s = '' if l == 1 else "s"
        text = f"\n{' ' * 7}- ".join((f"{t}: {l} new upload{s}:", *new_videos))
        self._message(text, "ok")

    def _end_message_handler(self) -> None:
        """End the instance message handler"""
        self._message_handler.end()

    def _init_message_handler(self) -> None:
        """Initialise and start the instance message handler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance message handler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _read_file(self, path: str) -> bool:
        """Read, parse, and store the contents of the given channel data JSON

        @param path Path to the channel data JSON.
        """
        self._message(f"Reading channel data file: {path}", "info")
        try:
            with open(path, "r") as fh:
                data = fh.read()
        except FileNotFoundError:
            self._message(f"File does not exist: {path}", "error")
            return False
        try:
            data_json = json.loads(data)
        except json.JSONDecodeError:
            self._message(
                f"Failed to parse file as JSON: {path}",
                "error")
            return False
        self.channel_data = data_json
        return True

    def _write_file(self, path: str, data) -> None:
        """Write the updated channel data JSON to the given file path

        Might need a try-except block or two.

        @param path File path for which to write channel data.
        @param data Channel data to write to the given path.
        """
        self._message(f"Writing channel data to file: {path}", "data")
        data = json.dumps(data, indent=2)
        with open(path, "w") as fh:
            fh.write(f"{data}\n")


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    cc = ChannelChecker(sys.argv[1])
    cc.run()
