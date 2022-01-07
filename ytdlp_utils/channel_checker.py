#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


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
            pass  # ---- TODO ----
        text = "All channels checked in {t:.1f}s"
        self._message(text.format(t=time.time() - time_start), "ok")
        self._end_message_handler()

    # ---- Private methods

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
            with open(file_path, "r") as fh:
                data = fh.read()
        except FileNotFoundError:
            self._message(f"File does not exist: {file_path}", "error")
            return False
        try:
            data_json = json.loads(data)
        except json.JSONDecodeError:
            self._message(
                f"Failed to parse file as JSON: {file_path}",
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
