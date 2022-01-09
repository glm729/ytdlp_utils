#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import time
import yt_dlp

from message_handler import MessageHandler


# Custom exceptions
# -----------------------------------------------------------------------------


class DownloadTooSlow(Exception):
    pass


# Support class definitions
# -----------------------------------------------------------------------------


class Video:

    _prefix_template = "\033[1;{colour}m{video_id}\033[0m"

    _stage_text = {
        0: "Video",
        1: "Audio",
    }

    def __init__(self, video_id: str, colour_index: int = 37):
        self.already_downloaded = False
        self.count_restart = 0
        self.count_slow = 0
        self.id = video_id
        self.progress = 0
        self.stage = 0
        self.time_start = None
        self._make_prefix(colour_index)

    # ---- Public methods

    def decrement_stage(self) -> None:
        """Decrement the instance download stage

        Guards against negative stages by setting to 0 if already at or below
        0.  The below-zero part may seem strange, but I've seen it happen
        somehow, probably to do with unlocked thread operations.
        """
        if self.stage <= 0:
            self.stage = 0
            return
        self.stage -= 1

    def get_stage(self, lower: bool = False) -> str:
        """Return text for the current stage

        @param lower Return the text as lowercase?
        @return Text informing of the current stage; capitalised or lowercase.
        """
        t = self._stage_text.get(self.stage, "Unknown stage")
        if lower:
            return t.lower()
        return t

    def increment_stage(self) -> None:
        """Increment the instance download stage

        Guards against excess stages by setting to 3 if already at or above 3.
        This may seem strange, but I've seen stages as high as 7 or 8 between
        checks somehow, probably from unlocked thread operations.
        """
        self.progress = 0
        if self.stage >= 3:
            self.stage = 3
            return
        self.stage += 1

    # ---- Private methods

    def _make_prefix(self, colour_index: int) -> None:
        """Set the prefix for the instance

        @param colour_index Shell escape colour to use for prefix text
        colouring.
        """
        self.prefix = self._prefix_template.format(
            colour=str(colour_index),
            video_id=self.id)


class CustomLogger:

    _skip_hints = (
        "[info]",
        "[youtube]",
        "Deleting original file")

    _warn_mkv = ''.join((
        "Requested formats are incompatible for merge ",
        "and will be merged into mkv"))

    def __init__(self, handler):
        self._handler = handler

    # ---- Public methods

    def debug(self, msg: str) -> None:
        """Log debug messages

        @param msg Debug message text.
        """
        if any(map(lambda x: msg.startswith(x), self._skip_hints)):
            return
        cv = self._handler._current_video
        if msg.endswith("has already been downloaded"):
            cv.already_downloaded = True
            return
        if msg.startswith("[Merger]"):
            self._message(f"{cv.prefix}: Merging data", "data")
            return
        if msg.startswith("[download]"):
            if msg.startswith("[download] Destination:"):
                text = "{p}: Downloading {s}".format(
                    p=cv.prefix,
                    s=cv.get_stage(lower=True))
                self._message(text, "info")
            return
        self._message(f"DBG: {msg}", "input")

    def error(self, msg: str) -> None:
        """Log error messages

        @param msg Error message text.
        """
        self._message(f"ERR: {msg}", "input")

    def info(self, msg: str) -> None:
        """Log info messages

        @param msg Info message text.
        """
        self._message(f"INF: {msg}", "input")

    def warning(self, msg: str) -> None:
        """Log warning messages

        @param msg Warning message text.
        """
        if msg == self._warn_mkv:
            return
        self._message(f"WRN: {msg}", "input")

    # ---- Private methods

    def _message(self, text: str, form: str) -> None:
        """Send a message from the logger via the handler

        @param text Message text.
        @param form Message form.
        """
        self._handler._message(text=text, form=form)


# DownloadHandler class definition
# -----------------------------------------------------------------------------


class DownloadHandler:

    _ytdlp_defaults = {
        "format": "/".join((
            "298+bestaudio",
            "136+bestaudio",
            "22",
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "outtmpl": "%(uploader)s/%(title)s.%(ext)s",
    }

    def __init__(
            self,
            video_ids,
            slow_count: int = 30,
            restart_count: int = 5):
        self._count_restart = restart_count
        self._count_slow = slow_count
        self._store_video_data(video_ids)

    # ---- Public methods

    def run(self) -> None:
        """Public run handler

        Initialises and starts the message handler.  Prepares yt_dlp.YoutubeDL
        options and object.  Ends the message handler.
        """
        self._init_message_handler()
        ytdlp_options = self._ytdlp_defaults.copy()
        ytdlp_options.update({
            "logger": CustomLogger(self),
            "progress_hooks": [
                self._progress_hook_downloading,
                self._progress_hook_finished,
            ],
        })
        self._message("Starting operations", "ok")
        time_start = time.time()
        with yt_dlp.YoutubeDL(ytdlp_options) as yt:
            self._run(yt)
        time_elapsed = time.time() - time_start
        text = "Downloads complete in {t:.1f}s".format(t=time_elapsed)
        if (l := len(self._failed)) > 0:
            self._message(text, "warn")
            s = '' if l == 1 else "s"
            t = f"\n{' ' * 7}- ".join((
                f"{l} download{s} failed:",
                *self._failed))
            self._message(t, "warn")
        else:
            self._message(text, "ok")
        self._close_message_handler()

    # ---- Private methods

    def _check_percentage(self, percentage: int) -> None:
        """Check percentage for the current download

        @param percentage Integer percentage from the current info dict.
        """
        cv = self._current_video
        floor_20_pc = percentage - (percentage % 20)
        if floor_20_pc >= (cv.progress + 20):
            text = "{p}: {s} download reached {v}% ({t:.1f}s)".format(
                p=cv.prefix,
                s=cv.get_stage(),
                v=str(floor_20_pc).rjust(3, " "),
                t=time.time() - cv.time_start)
            self._message(text, "info")
            cv.progress = floor_20_pc

    def _check_speed(self, speed: float) -> None:
        """Check speed of the current download

        @param speed Speed of the download in bytes per second, from the
        current info dict.
        """
        slow = (speed / (1024 ** 2)) < 1
        update = 0
        cv = self._current_video
        if slow:
            update = cv.count_slow + 1
            if update > self._count_slow:
                cv.count_slow = 0
                if (cv.count_restart + 1) > self._count_restart:
                    self._restart_limit_reached()
                else:
                    self._restart_slow()
                raise DownloadTooSlow()
        cv.count_slow = update

    def _close_message_handler(self) -> None:
        """End the instance MessageHandler"""
        self._message_handler.end()

    def _init_message_handler(self) -> None:
        """Initialise and start the instance MessageHandler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance MessageHandler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _progress_hook_downloading(self, data) -> None:
        """Callback for the "downloading" stage

        @param data Data provided by the yt_dlp.YoutubeDL object.
        """
        if not data.get("status") == "downloading":
            return
        bytes_current = data.get("downloaded_bytes")
        bytes_total = data.get("total_bytes")
        speed = data.get("speed")
        percentage = round((bytes_current / bytes_total) * 100)
        self._check_percentage(percentage)
        if speed is not None:
            self._check_speed(speed)

    def _progress_hook_finished(self, data) -> None:
        """Callback for the "finished" stage

        @param data Data provided by the yt_dlp.YoutubeDL object.
        """
        if not data.get("status") == "finished":
            return
        cv = self._current_video
        self._current_video.increment_stage()

    def _restart_limit_reached(self) -> None:
        """Notify of reaching the restart limit for the current video

        Pop the current video to the failed videos list.
        """
        text = "{p}: Restart limit reached"
        self._message(text.format(p=self._current_video.prefix), "warn")
        self._failed.append(self._remaining.pop(0))

    def _restart_slow(self) -> None:
        """Notify of reaching the slow-speed limit for the current video"""
        cv = self._current_video
        cv.count_restart += 1
        r = self._count_restart - cv.count_restart
        text = "{p}: Reached slow speed limit, restarting (remaining: {r})"
        self._message(text.format(p=cv.prefix, r=r), "warn")

    def _run(self, yt) -> None:
        """Private run function, to abstract control methods

        @param yt yt_dlp.YoutubeDL object.
        """
        text = {
            "already_downloaded": "{p}: Video already downloaded",
            "end": "{p}: Video downloaded and merged in {t:.1f}s",
            "start": "{p}: Starting download",
        }
        self._failed = []
        self._remaining = list(self._video_data.keys())
        while True:
            try:
                self._current_video = self._video_data.get(self._remaining[0])
                cv = self._current_video
                self._message(text.get("start").format(p=cv.prefix), "ok")
                cv.time_start = time.time()
                yt.download((cv.id,))
                cv.time_end = time.time()
                cv.time_elapsed = cv.time_end - cv.time_start
                if cv.already_downloaded:
                    self._message(
                        text.get("already_downloaded").format(p=cv.prefix),
                        "ok")
                else:
                    self._message(
                        text.get("end").format(p=cv.prefix, t=cv.time_elapsed),
                        "ok")
                self._remaining.pop(0)
            except DownloadTooSlow:
                continue
            if len(self._remaining) == 0:
                break
        pass  # TODO: Post-processing

    def _store_video_data(self, video_ids) -> None:
        """Store video data in the instance, given a set of video IDs

        @param video_ids List or tuple of strings; IDs or links to the youtube
        videos to attempt to download.
        """
        colour_index = 30
        self._video_data = {}
        for video_id in video_ids:
            self._video_data.update({
                video_id: Video(video_id, colour_index=colour_index),
            })
            if colour_index >= 37:
                colour_index = 30
                continue
            colour_index += 1


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    dh = DownloadHandler(sys.argv[1:])
    dh.run()
