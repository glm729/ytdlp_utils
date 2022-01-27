#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import time
import yt_dlp

from message_handler import MessageHandler
from playlist import Playlist
from video import Video


# Custom exceptions
# -----------------------------------------------------------------------------


class DownloadTooSlow(Exception):
    pass


# Support class definitions
# -----------------------------------------------------------------------------


class CustomLogger:

    _skip_hints = (
        "[dashsegments]",
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
        if not hasattr(self._handler, "_current_video"):
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


class PlaylistHandler:

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
            playlist_id,
            slow_count: int = 30,
            restart_count: int = 5):
        self._count_restart = restart_count
        self._count_slow = slow_count
        self.playlist = Playlist(playlist_id)

    # ---- Public methods

    def run(self) -> None:
        """Public run handler

        Initialises and starts the message handler.  Prepares yt_dlp.YoutubeDL
        options and object.  Ends the message handler.
        """
        self._init_message_handler()
        # Add logger and progress hooks to the defaults
        self._ytdlp_defaults.update({
            "logger": CustomLogger(self),
            "progress_hooks": [
                self._progress_hook_downloading,
                self._progress_hook_finished,
            ],
        })
        # Make a copy of the defaults for requesting playlist data
        ytdlp_options_request = self._ytdlp_defaults.copy()
        ytdlp_options_request.update({ "extract_flat": True, })
        # Request and store the playlist data
        self._message("Requesting playlist data", "ok")
        with yt_dlp.YoutubeDL(ytdlp_options_request) as yt:
            data = self.playlist.request_data(yt)
        l = data.get("length")
        text = "Found {l} video{s}".format(l=l, s='' if l == 1 else "s")
        self._message(text, "ok")
        self._store_video_data(data.get("entries"))
        # Download the videos
        self._message("Starting downloads", "ok")
        time_start = time.time()
        self._run(yt)
        time_elapsed = time.time() - time_start
        text = "Downloads complete in {t:.1f}s".format(t=time_elapsed)
        # Check for any failed videos
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

    def _check_percentage(
            self,
            cv: Video,
            numerator: int,
            denominator: int,
            dash: bool = False) -> None:
        """Check percentage for the current download

        @param cv Current video being downloaded.
        @param numerator Numerator for the percentage calculation.
        @param denominator Denominator for the percentage calculation.
        @param dash Is this a DASH video calculation?
        """
        try:
            percentage = round((numerator / denominator) * 100)
        except TypeError:
            return
        floor_20_pc = percentage - (percentage % 20)
        if floor_20_pc >= (cv.progress + 20):
            if dash:
                (n, d) = (str(numerator), str(denominator))
                f = "fragment {i} of {t}; ".format(i=n.rjust(len(d), " "), t=d)
            else:
                f = ''
            text = "{p}: {s} download reached {v}% ({f}{t:.1f}s)".format(
                p=cv.prefix,
                s=cv.get_stage(),
                v=str(floor_20_pc).rjust(3, " "),
                f=f,
                t=time.time() - cv.time_start)
            self._message(text, "info")
            cv.progress = floor_20_pc

    def _check_speed(
            self,
            cv: Video,
            speed: float,
            dash: bool = False) -> None:
        """Check speed of the current download

        @param cv Current video being downloaded.
        @param speed Speed of the download in bytes per second, from the
        current info dict.
        @param dash Is this a DASH video calculation?
        """
        try:
            slow = (speed / (1024 * (512 if dash else 1024))) > 1
        except TypeError:
            return
        update = 0
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
        if data.get("info_dict").get("fragments", None) is not None:
            if not (cv := self._current_video)._dash_notified:
                text = ''.join((
                    f"{cv.prefix}: Video is DASH; minimum speed halved ",
                    "and progress notifications modified"))
                self._message(text, "warn")
                cv._dash_notified = True
            numerator = data.get("fragment_index")
            denominator = data.get("fragment_count")
            dash = True
        else:
            numerator = data.get("downloaded_bytes")
            denominator = data.get("total_bytes")
            dash = False
        speed = data.get("speed")
        self._check_percentage(
            self._current_video,
            numerator,
            denominator,
            dash)
        self._check_speed(self._current_video, speed)

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
        # TODO: Change handling failed videos to keep playlist context
        self._remaining = list(self._video_data.keys())
        while True:
            try:
                self._current_video = self._video_data.get(self._remaining[0])
                cv = self._current_video
                ytdlp_options_dl = self._ytdlp_defaults.copy()
                ytdlp_options_dl.update({ "outtmpl": cv.outtmpl, })
                self._message(text.get("start").format(p=cv.prefix), "ok")
                cv.time_start = time.time()
                with yt_dlp.YoutubeDL(ytdlp_options_dl) as yt:
                    yt.download((cv.id,))
                # TODO: try...except TimeoutError
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

    def _store_video_data(self, video_data) -> None:
        """Store video data in the instance, given a set of video IDs

        @param video_data List or tuple of strings; IDs or links to the youtube
        videos to attempt to download.
        """
        colour_index = 29
        self._video_data = {}
        for data in video_data:
            if colour_index >= 37:
                colour_index = 30
            else:
                colour_index += 1
            video = Video(data.get("id"))
            video.outtmpl = data.get("outtmpl")
            i = str(data.get("index"))
            text = "Video {i} / {t}".format(
                i=i.rjust(len(self.playlist.length_str), " "),
                t=self.playlist.length_str)
            video.prefix = "\033[1;{c}m{t}\033[0m".format(
                c=colour_index,
                t=text)
            self._video_data.update({ data.get("id"): video, })


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    dh = PlaylistHandler(sys.argv[1])
    dh.run()
