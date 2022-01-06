#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import time
import yt_dlp

from message_handler import MessageHandler


# Custom exceptions
# -----------------------------------------------------------------------------


class InterruptSpeed(Exception):
    pass


# Helper class definitions
# -----------------------------------------------------------------------------


class Video:

    _prefix_template = "\033[1;{c}m{i}\033[0m"

    def __init__(self, video_id: str, colour_index: int = 37):
        prefix = self._prefix_template.format(c=colour_index, i=video_id)
        defaults = (
            ("count_restart", 0),
            ("count_slow", 0),
            ("id", video_id),
            ("prefix", prefix),
            ("progress", 0),
            ("stage", 0),
            ("time_start", None))
        for (k, v) in defaults:
            setattr(self, k, v)

    # ---- Public methods

    def decrement_stage(self):
        """Decrement the instance stage"""
        self.stage -= 1

    def get_stage_text(self, lower=False):
        """Return text for the current video download stage

        @param lower Should the text be returned as lowercase?
        """
        if self.stage == 0:
            text = "Video"
        elif self.stage == 1:
            text = "Audio"
        else:
            text = "Unknown stage"
        if lower:
            return text.lower()
        return text

    def increment_stage(self):
        """Increment the instance stage"""
        self.stage += 1
        self.progress = 0

    def set_time_start(self):
        """Set the `time_start` attribute for the instance"""
        self.time_start = time.time()


# Custom logger class definition
# -----------------------------------------------------------------------------


class DownloadHandlerLogger:

    # ---- Attributes

    _merge_warning = ''.join((
        "Requested formats are incompatible for merge ",
        "and will be merged into mkv"))

    _skip_hints = ("Deleting original file", "[info]")

    # ---- Constructor

    def __init__(self, download_handler):
        self._handler = download_handler

    # ---- Public methods (for yt_dlp.YoutubeDL)

    def debug(self, message):
        """Log debug messages

        @param message Debug message text.
        """
        if any(map(lambda x: message.startswith(x), self._skip_hints)):
            return
        if message.startswith(y := "[youtube]"):
            video_id = message.split(":")[0].split(" ")[1]
            if video_id != (c := self._handler._current_video):
                if c is not None:
                    previous = self._handler._get_current_video_data()
                    text = "{p}: Video downloaded and merged in {t:.1f}s"
                    self._message(
                        text.format(
                            p=previous.prefix,
                            t=time.time() - previous.time_start),
                        "ok")
                self._handler._set_current_video(video_id)
                text = "{p}: Starting download".format(
                    p=self._handler._get_current_video_data().prefix)
                self._message(text, "ok")
                self._handler._video_data.get(video_id).set_time_start()
            return
        if message.startswith("[download] Destination:"):
            video_current = self._handler._get_current_video_data()
            text = "{p}: Downloading {s}".format(
                p=video_current.prefix,
                s=video_current.get_stage_text(lower=True))
            self._message(text, "info")
            return
        if message.startswith("[Merger]"):
            text = "{p}: Merging data".format(
                p=self._handler._get_current_video_data().prefix)
            self._message(text, "info")
            return
        if message.startswith("[download]"):
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
        # Ignore the merge warning
        if message == self._merge_warning:
            return
        self._message(message, "warn")

    # ---- Private methods

    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance MessageHandler

        @param text Message text.
        @param form Message form.
        """
        self._handler._message_handler.message(text=text, form=form)


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

    def __init__(self, video_ids):
        self._store_video_data(video_ids)

    # ---- Public methods

    def run(self) -> None:
        """Main public run method"""
        self._init_message_handler()
        self._logger = DownloadHandlerLogger(self)  # wooo
        ytdlp_opts = self._ytdlp_options.copy()
        ytdlp_opts.update({
            "logger": self._logger,
            "progress_hooks": [
                self._progress_hook_downloading,
                self._progress_hook_finished
            ],
        })
        self._message("Starting operations", "ok")
        time_start = time.time()
        with yt_dlp.YoutubeDL(ytdlp_opts) as yt:
            yt.download(self._video_data.keys())
        last = self._get_current_video_data()
        text_last = "{p}: Video downloaded and merged in {t:.1f}s".format(
            p=last.prefix,
            t=time.time() - last.time_start)
        self._message(text_last, "ok")
        text_end = "Videos downloaded and merged in {t:.1f}s"
        self._message(text_end.format(t=time.time() - time_start), form="ok")
        self._end_message_handler()

    # ---- Private methods

    def _check_percentage(self, video_id: str, percentage: int) -> None:
        """Check percentage for the current download

        @param video_id ID of the current video download.
        @param percentage Integer percentage from the current info dict.
        """
        data = self._video_data.get(video_id)
        floor_20_pc = percentage - (percentage % 20)
        if floor_20_pc >= (data.progress + 20):
            text = "{p}: {s} download reached {v}% ({t:.1f}s)".format(
                p=data.prefix,
                s=data.get_stage_text(),
                v=str(floor_20_pc).rjust(3, " "),
                t=time.time() - data.time_start)
            self._message(text, "info")
            self._video_data.get(video_id).progress = floor_20_pc

    def _check_speed(self, speed: float) -> None:
        """Check speed of the current download

        @param speed Speed of the download in bytes per second, from the
        current info dict.
        """
        pass

    def _end_message_handler(self) -> None:
        """Close the instance MessageHandler"""
        self._message_handler.end()

    def _get_current_video_data(self):
        """Return the dataset for the current video ID"""
        return self._video_data.get(self._current_video)

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
        video_id = data.get("info_dict").get("id")
        total_bytes = data.get("total_bytes")
        current_bytes = data.get("downloaded_bytes")
        speed = data.get("speed")
        percentage = round((current_bytes / total_bytes) * 100)
        self._check_percentage(video_id, percentage)
        self._check_speed(speed)

    def _progress_hook_finished(self, data) -> None:
        """Custom progress hook for the "finished" status

        @param data Data provided to the hook callback by the yt_dlp.YoutubeDL
        instance.  Appears to be a LazyList.
        """
        if not data.get("status") == "finished":
            return
        video_id = data.get("info_dict").get("id")
        self._video_data.get(video_id).increment_stage()

    def _set_current_video(self, video_id: str) -> None:
        """Set the current video ID for the instance

        @param video_id Video ID to set as the current video.
        """
        self._current_video = video_id

    def _store_video_data(self, video_ids) -> None:
        """Store a structured set of video data in the instance

        @param video_ids List or tuple of youtube video IDs.
        """
        colour_index = 30
        data = {}
        template = "\033[1;{c}m{i}\033[0m"
        for video_id in video_ids:
            data.update({ video_id: Video(video_id, colour_index) })
            if colour_index >= 37:
                colour_index = 30
                continue
            colour_index += 1
        self._video_data = data
        self._current_video = None


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    dh = DownloadHandler(["A7xhz56RaxY", "ZdjcHv8xkjg"])
    dh.run()
