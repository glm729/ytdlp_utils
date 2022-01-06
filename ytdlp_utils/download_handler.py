#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import yt_dlp

from message_handler import MessageHandler


# Custom exceptions
# -----------------------------------------------------------------------------


class InterruptSpeed(Exception):
    pass


# Custom logger class definition
# -----------------------------------------------------------------------------


class DownloadHandlerLogger:

    # ---- Attributes

    _merge_warning = ''.join((
        "Requested formats are incompatible for merge ",
        "and will be merged into mkv"))

    _skip_hints = (
        "Deleting original file",
        "[download]",
        "[info]",
        "[youtube]")

    # ---- Constructor

    def __init__(self, message_handler: MessageHandler):
        self._message_handler = message_handler

    # ---- Public methods (for yt_dlp.YoutubeDL)

    def debug(self, message):
        """Log debug messages

        @param message Debug message text.
        """
        if any(map(lambda x: message.startswith(x), self._skip_hints)):
            return
        if message.startswith("[Merger] Merging formats into"):
            self._message("Merging", "data")
            return
        self._message(message, "data")

    def error(self, message):
        """Log error messages

        @param message Error message text.
        """
        self._message(message, "error")

    def info(self, message):
        """Log info messages

        @param message Info message text.
        """
        self._message(message, "info")

    def warning(self, message):
        """Log warning messages

        @param message Warning message text.
        """
        if message == self._merge_warning:
            self._message("Formats will be merged", "warn")
            return
        self._message(message, "warn")

    # ---- Private methods

    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance MessageHandler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)


# Class definition
# -----------------------------------------------------------------------------


class DownloadHandler:

    # ---- Instance defaults

    _ytdlp_options = {
        "format": "/".join((
            "298+bestaudio",
            "136+bestaudio",
            "22",
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "outtmpl": "TESTING__%(uploader)s__%(title)s.%(ext)s"
    }

    # ---- Constructor

    def __init__(self):
        pass

    # ---- Public methods

    def run(self, links) -> None:
        """Main public run method

        @param links Video links to attempt to download.
        """
        self._init_message_handler()
        ytdlp_opts = self._ytdlp_options.copy()
        ytdlp_opts.update({
            "logger": DownloadHandlerLogger(self._message_handler),
            "progress_hooks": [
                self._progress_hook_downloading,
                self._progress_hook_finished
            ],
        })
        self._message("Starting", "ok")
        with yt_dlp.YoutubeDL(ytdlp_opts) as yt:
            yt.download(links)
        self._message("Ending", "ok")
        self._end_message_handler()

    # ---- Private methods

    def _end_message_handler(self) -> None:
        """Close the instance MessageHandler"""
        self._message_handler.end()

    def _init_message_handler(self) -> None:
        """Instantiate and start the instance MessageHandler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance MessageHandler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _progress_hook_downloading(self, data) -> None:
        """Custom progress hook for the "downloading" status

        @param data Data provided to the hook callback by the yt_dlp.YoutubeDL
        instance.  Appears to be a LazyList.
        """
        if not data.get("status") == "downloading":
            return
        self._message("Downloading...", "info")
        # TODO: This hook could be used to check download progress!

    def _progress_hook_finished(self, data) -> None:
        """Custom progress hook for the "finished" status

        @param data Data provided to the hook callback by the yt_dlp.YoutubeDL
        instance.  Appears to be a LazyList.
        """
        if not data.get("status") == "finished":
            return
        self._message("Finished stage!", "ok")
        # TODO: This hook could be used to increment the stage!


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    dh = DownloadHandler()
    dh.run(["A7xhz56RaxY"])
