#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import re
import subprocess
import threading
import time

from message import Message


# Class definition
# -----------------------------------------------------------------------------


class PlaylistHandler:

    # ---- Atomic-type instance vars

    _ok = True

    _playlist_length = None

    _restart = True

    _waiting = True

    # ---- Collection-type instance vars

    _error_message = {
        104: ''.join((
            "WARNING: [youtube] Unable to download webpage: ",
            "<urlopen error [Errno 104] Connection reset by peer>")),
        110: ''.join((
            "ERROR: unable to download video data: ",
            "<urlopen error [Errno 110] Connection timed out>"))
    }

    _line_start = {
        "merging": "[Merger] Merging formats into",
        "stage": "[download] Destination:"
    }

    _rex = {
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s"))),
        "video_index": re.compile(
            r"^\[download\] Downloading video (?P<i>\d+) of (?P<n>\d+)"),
    }

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

    # ---- Constructor

    def __init__(self, playlist_id, slow_count=30, restart_count=10):
        self._slow_count = slow_count
        self._restart_count = restart_count
        self._playlist = {
            "id": playlist_id,
            "index": None,
            "length": None
        }

    # ---- Public methods

    def run(self):
        """Public run handler method to attempt to download the playlist"""
        self._init_message_handler()
        self._message("Starting playlist download", "ok")
        time_start = time.time()
        while self._restart:
            self._new_process()
            self._wait()
        time_end = time.time() - time_start
        if self._ok:
            t = f"Playlist downloads completed in {time_end:.1f}s"
            f = "ok"
        else:
            t = f"Playlist downloads failed at {time_end:.1f}s"
            f = "error"
        self._message(t, f)
        self._close_message_handler()

    # ---- Private methods

    def _close_message_handler(self):
        """Tear down the message handling components"""
        self._queue_message.join()
        self._waiting = False
        self._thread_message.join()

    def _fun_thread_message(self):
        """Message thread function"""
        while self._waiting:
            try:
                self._print_message(self._queue_message.get(timeout=0.2))
                self._queue_message.task_done()
            except queue.Empty:
                pass

    def _fun_thread_stderr(self, stderr):
        """Stderr thread function

        @param stderr Stderr of the current subprocess.
        """
        while (l := stderr.readline()):
            line = l.decode("utf-8").strip()
            if line == self._error_message.get(104):
                self._restart(cause=0x0104)
                continue
            if line == self._error_message.get(110):
                self._restart(cause=0x0110)
                continue

    def _fun_thread_stdout(self, stdout):
        """Stdout thread function

        @param stdout Stdout of the current subprocess.
        """
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()
            # Check if the current video is at the merging stage
            if line.startswith(self._line_start.get("merging")):
                self._increment_video_stage()
                self._message("Merging data", "info")
                continue
            # Check if the current video has progressed to the next stage
            if line.startswith(self._line_start.get("stage")):
                stage = self._get_video_stage()
                if stage == 0:
                    self._message("Downloading video", "info")
                elif stage == 1:
                    self._message("Downloading audio", "info")
                    self._current_video.update({ "progress": 0 })
                self._increment_stage()
                continue
            # Check the progress of the current video download
            if (cp := self._rex.get("progress").search(line)) is not None:
                data = cp.groupdict()
                if (percentage := data.get("pc", None)) is not None:
                    self._check_percentage(
                        percentage,
                        self._current_video.get("time_start"))
                if (speed := data.get("sp", None)) is not None:
                    self._check_speed(speed)
                continue
            # Check the video index in the playlist
            if (vi := self._rex.get("video_index").search(line)) is not None:
                data = vi.groupdict()
                (i, n) = (data.get("i"), data.get("n"))
                self._playlist_index = i
                if self._playlist_length is None:
                    self._playlist_length = n
                    self._index_pad = len(n)
                _i = i.rjust(self._index_pad, " ")
                self._message(f"Downloading video {_i} of {n}", "info")
                continue

    def _generate_command(self, index_start):
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
            index_start,
            self._playlist.get("id"))

    def _increment_video_stage(self):
        """Increment the recorded stage of the current video download"""
        stage = self._current_video.get("stage")
        if stage >= 3:
            self._message(f"Current stage is {stage}, ignoring increment call")
            return
        self._current_video.update({ "stage": stage + 1 })

    def _init_message_handler(self):
        """Initialise the message handling components

        Initialises recursive lock, message queue, and message thread.  Starts
        the message thread immediately.
        """
        self._lock = threading.RLock()
        self._queue_message = queue.Queue()
        self._thread_message = threading.Thread(
            target=self._fun_thread_message,
            daemon=True)
        self._thread_message.start()

    def _init_current_video(self):
        """Initialise or overwrite data for the current video download"""
        self._current_video = {
            "progress": 0,
            "stage": 0
        }

    def _message(self, t, f):
        """Enqueue a message to print

        @param t Message text.
        @param f Message format.
        """
        self._lock.acquire()
        try:
            self._queue_message.put(Message(t, form=f))
        finally:
            self._lock.release()

    def _new_process(self):
        pass

    def _print_message(self, msg):
        """Attempt to safely print a message from the message queue

        @param msg Message to print while locked.
        """
        self._lock.acquire()
        try:
            msg.print()
        finally:
            self._lock.release()

    def _wait(self):
        pass


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    pass
