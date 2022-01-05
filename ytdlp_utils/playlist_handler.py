#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import re
import subprocess
import threading
import time

from message_handler import MessageHandler


# Class definitions
# -----------------------------------------------------------------------------


class Playlist:

    def __init__(self, playlist_id, index=1, length=1):
        self.id = playlist_id
        self.length = length
        self.length_str = str(length)
        self.set_index(index)

    # ---- Public methods

    def get_playlist_data(self):
        """Request the data for the playlist

        Primarily for the purpose of discovering and storing playlist length.
        """
        cmd = ("yt-dlp", "--flat-playlist", "--print", "id", self.id)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if proc.wait() == 0:
            count = 0
            while (l := proc.stdout.readline()):
                count += 1
            self.length = count
            self.length_str = str(count)
            self.set_index(self.index)
        # TODO: Subprocess failure is currently unhandled!
        # This gap may be adequately handled by the defaults.

    def set_index(self, index):
        """Set the current index for the playlist instance

        @param index Index to set as current.
        """
        self.index = index
        self.index_str = str(index)
        self.index_padded = self.index_str.rjust(len(self.length_str), " ")


class Video:

    def __init__(
            self,
            video_id=None,
            progress=0,
            stage=0,
            slow_count=0,
            restart_count=0,
            time_start=0.0):
        self.id = video_id
        self.progress = progress
        self.stage = stage
        self.slow_count = slow_count
        self.restart_count = restart_count
        self.time_start = time_start
        self.time_end = None
        self._guard = False

    # ---- Public methods

    def decrement_stage(self):
        """Decrement the video stage

        Does not check for a guard when decrementing.
        """
        self.stage -= 1

    def get_stage_text(self):
        """Return appropriate text for the current video download stage"""
        if self.stage == 1:
            return "Video"
        if self.stage == 2:
            return "Audio"
        return "Unknown"

    def guard(self):
        """Set the guard"""
        self._guard = True

    def increment_stage(self):
        """Increment the video stage

        Checks for a guard, and removes the guard if present, instead of
        incrementing the stage.
        """
        if self._guard:
            self._guard = False
            return
        self.stage += 1

    def is_guarded(self):
        """Return the guarded state of the video"""
        return self._guard

    def unguard(self):
        """Unset the guard"""
        self._guard = False


# Handler class definition
# -----------------------------------------------------------------------------


class PlaylistHandler:

    # ---- Atomic-type instance vars

    _colour_index = 30

    _loop = True

    _ok = True

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

    _failed = []

    _line_start = {
        "end": "[download] Finished downloading playlist:",
        "merging": "[Merger] Merging formats into",
        "merging_warning": ''.join((
            "WARNING: Requested formats are incompatible for merge ",
            "and will be merged into")),
        "stage": "[download] Destination:"
    }

    _rex = {
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s"))),
        "video_index": re.compile(
            r"^\[download\] Downloading video (?P<i>\d+) of (?P<n>\d+)")
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

    def __init__(
            self,
            playlist_id,
            index_start=1,
            slow_count=30,
            restart_count=10):
        self._slow_count = slow_count
        self._restart_count = restart_count
        self._playlist = Playlist(playlist_id)
        self._playlist.set_index(index_start)

    # ---- Public methods

    def run(self):
        """Public run handler method to attempt to download the playlist"""
        self._init_message_handler()
        self._message("Requesting playlist data", "info")
        self._playlist.get_playlist_data()
        t = f"Playlist is of length {self._playlist.length_str}"
        self._message(t, "ok")
        self._message("Starting playlist download", "ok")
        time_start = time.time()
        while self._loop:
            self._new_process()
            self._wait()
        time_end = time.time() - time_start
        t = f"Playlist downloads completed in {time_end:.1f}s"
        if self._ok:
            self._message(t, "ok")
        else:
            self._message(t, "warn")
            l = len(self._failed)
            s = '' if l == 1 else "s"
            t = "\n- ".join((
                f"{l} video{s} failed to download:",
                *self._failed))
            self._message(t, form="warn")
        self._end_message_handler()

    # ---- Private methods

    def _check_percentage(self, percentage: str) -> None:
        """Check the percentage of the current video or audio download

        @param percentage Regex-captured text for the current percentage.
        @param time_start Start time of the current video download, for more
        interesting messages.
        """
        pc = int(percentage.split(".")[0])
        rpc = pc - (pc % 20)
        if rpc >= (self._current_video.progress + 20):
            self._current_video.progress = rpc
            time_now = time.time() - self._current_video.time_start
            t = ''.join((
                f"{self._message_prefix()}: ",
                f"{self._current_video.get_stage_text()} download reached ",
                f"{str(rpc).rjust(3, ' ')}% ({time_now:.1f}s)"))
            self._message(t, "info")

    def _check_speed(self, speed: str) -> None:
        """Check the speed of the current video or audio download

        @param speed Regex-captured text for the current speed.
        """
        update_value = 0
        if speed.endswith("K"):
            update_value = self._current_video.slow_count + 1
            if update_value > self._slow_count:
                self._restart(cause=0x2510)
                return
        self._current_video.slow_count = update_value

    def _end_message_handler(self):
        """End the message handler operations"""
        self._message_handler.end()

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
            # Debug check for unhandled stderr
            if not line.startswith(self._line_start.get("merging_warning")):
                self._message(f"DEBUG:\n{line}", "error")

    def _fun_thread_stdout(self, stdout):
        """Stdout thread function

        @param stdout Stdout of the current subprocess.
        """
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()
            # Check if the current video is at the merging stage
            if line.startswith(self._line_start.get("merging")):
                t = f"{self._message_prefix()}: Merging data"
                self._current_video.increment_stage()
                self._message(t, "info")
                continue
            # Check if the current video has progressed to the next stage
            if line.startswith(self._line_start.get("stage")):
                t = f"{self._message_prefix()}: Downloading"
                stage = self._current_video.stage
                if stage == 0:
                    self._message(f"{t} video", "info")
                elif stage == 1:
                    self._message(f"{t} audio", "info")
                    self._current_video.progress = 0
                self._current_video.increment_stage()
                continue
            # Check the progress of the current video download
            if (cp := self._rex.get("progress").search(line)) is not None:
                data = cp.groupdict()
                if (percentage := data.get("pc", None)) is not None:
                    self._check_percentage(percentage)
                if (speed := data.get("sp", None)) is not None:
                    self._check_speed(speed)
                continue
            # Check the video index in the playlist
            if self._rex.get("video_index").search(line) is not None:
                if hasattr(self, "_current_video"):
                    if self._current_video.is_guarded():
                        self._current_video.unguard()
                    else:
                        self._notify_video_downloaded()
                        self._increment_playlist_index()
                t = "Downloading video {i} of {n}".format(
                    i=self._playlist.index_padded,
                    n=self._playlist.length_str)
                self._message(t, "info")
                self._current_video = Video(time_start=time.time())
                continue
            # Check if the playlist download has ended
            if line.startswith(self._line_start.get("end")):
                self._notify_video_downloaded()
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
            self._playlist.id)

    def _increment_playlist_index(self):
        """Increment the playlist index, or cancel if video is guarded

        Unguard the video if guarded.  End the instance loop if at the end of
        the playlist.
        """
        i = self._playlist.index
        if i == self._playlist.length:
            self._loop = False
            return
        self._playlist.set_index(i + 1)
        if self._colour_index >= 37:
            self._colour_index = 30
            return
        self._colour_index += 1

    def _init_message_handler(self):
        """Initialise the message handling components

        Initialises recursive lock, message queue, and message thread.  Starts
        the message thread immediately.
        """
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _join_check_threads(self):
        """Join the stdout and stderr check threads"""
        self._thread_stdout.join()
        self._thread_stderr.join()

    def _message(self, text: str, form: str) -> None:
        """Enqueue a message to print, via the message handler

        @param text Message text.
        @param form Message format.
        """
        self._message_handler.message(text=text, form=form)

    def _message_prefix(self):
        """Generate a message prefix for the current video"""
        return "\033[1;{c}mVideo {i} / {l}\033[0m".format(
            c=self._colour_index,
            i=self._playlist.index_padded,
            l=self._playlist.length)

    def _new_process(self):
        """Start a new download subprocess

        Also initialises and starts stdout- and stderr-check threads.
        """
        # Open subprocess
        self._proc = subprocess.Popen(
            self._generate_command(self._playlist.index_str),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        # Initialise stdout and stderr threads
        self._thread_stdout = threading.Thread(
            target=self._fun_thread_stdout,
            args=(self._proc.stdout,),
            daemon=True)
        self._thread_stderr = threading.Thread(
            target=self._fun_thread_stderr,
            args=(self._proc.stderr,),
            daemon=True)
        # Start stdout and stderr threads
        self._thread_stdout.start()
        self._thread_stderr.start()

    def _notify_video_downloaded(self):
        """Provide a message upon ending a video download"""
        time_end = time.time() - self._current_video.time_start
        self._current_video.time_end = time_end
        t = "{p}: Video downloaded and merged in {t:.1f}s"
        self._message(t.format(p=self._message_prefix(), t=time_end), "ok")

    def _restart(self, cause):
        """Kill and restart the instance subprocess

        Checks restart count for the current video.  If exceeding the max.
        number of restarts, provides an error message, and increments the
        playlist index.

        @param cause Internal code representing cause of the restart, for more
        meaningful message text.
        """
        self._proc.kill()
        rsc = self._current_video.restart_count + 1
        if rsc > self._restart_count:
            self._ok = False
            self._failed.append(self._playlist.index_padded)
            t = f"{self._message_prefix()}: Restart limit reached"
            self._message(t, "error")
            self._increment_playlist_index()
            return
        if cause == 0x0104:
            e = "Connection reset, restarting at current index"
        elif cause == 0x0110:
            e = "Timeout, restarting at current index"
        elif cause == 0x0403:
            e = "Received HTTP error 403, restarting at current index"
        elif cause == 0x2510:
            e = "Reached slow speed limit, restarting"
        self._message(f"{self._message_prefix()}: {e}", "warn")
        self._current_video.guard()

    def _wait(self):
        """Wait for the instance process to end

        Joins stdout and stderr check threads, and stops the operations loop if
        all downloads are successful.
        """
        self._proc.wait()
        self._join_check_threads()
        if self._proc.returncode == 0:
            self._loop = False


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    pass
