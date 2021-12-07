#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import re
import subprocess
import threading
import time

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlSubprocessRunner:

    _ok = True

    _restart = True

    _stage = 0

    _opt = {
        "format": "/".join((
            "298+bestaudio",
            "136+bestaudio",
            "22",
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "output": "%(uploader)s/%(title)s.%(ext)s"
    }

    _rex = {
        "merging": re.compile(r"^\[Merger\] Merging formats into"),
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s"))),
        "stage": re.compile(r"^\[download\] Destination:")
    }

    def __init__(self, video_id, slow_count=30, restart_count=10):
        self._store_data(video_id)
        self.slow_count = slow_count
        self.restart_count = restart_count

    # ---- Public methods

    def run(self):
        """Public runner method to attempt to download the given video

        Initialises message queue and thread, and runs a new process until the
        download is complete or until the restart limit is reached.  Provides
        notification of success or failure, and closes the message queue and
        thread at end.
        """
        self._init_mq()
        self._message("Starting download", "ok")
        self._time_start = time.time()
        while self._restart:
            self._new_process()
            self._wait()
        time_end = time.time() - self._time_start
        if self._ok:
            t = f"Video downloaded and merged in {time_end:.1f}s"
            f = "ok"
        else:
            t = f"Video download failed after {time_end:.1f}s"
            f = "error"
        self._message(t, f)
        self._close_mq()

    # ---- Private methods ----

    def _build_cmd(self):
        """Return the command for running yt-dlp

        Tuple of strings, in a specified format, and with specific options for
        yt-dlp (e.g. `--newline`).

        @return Tuple of strings, to pass to `subprocess.Popen`
        """
        return (
            "yt-dlp",
            "--force-ipv4",
            "--geo-bypass",
            "--newline",
            "--format",
            self._opt.get("format"),
            "--output",
            self._opt.get("output"),
            f"https://www.youtube.com/watch?v={self._id}")

    def _check_line_stderr(self, stderr):
        """Thread function to check stderr in-process

        Currently mostly a dummy, but will perhaps attempt to restart if
        receiving a 403.  Upon implementing this, no more 403s were received,
        so it is currently untested.

        @param stderr Stderr of the opened subprocess
        """
        while (l := stderr.readline()):
            line = l.decode("utf-8").strip()
            #=> DEBUG
            # t = f"\n{' ' * 7}".join(("STDERR:", line))
            # self._message(t, "warn")
            #<=
            if line.endswith("HTTP Error 403: Forbidden"):
                self._restart(cause=0x0403)

    def _check_line_stdout(self, stdout, time_start):
        """Thread function to check stdout in-process

        A bit complex, and perhaps should be broken up a little.  Uses regex
        parsing to check the current stage of the download / subprocess call.
        Hierarchically checks if merging, changing stage, or downloading.
        Provides messages when merging or changing stage, and passes progress
        information to `_check_percentage` and `_check_speed` for further
        checks and messages.

        @param stdout Stdout of the opened subprocess
        @param time_start Start time of the subprocess, for more interesting
        messages.
        """
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()
            check_merging = self._rex["merging"].search(line)
            check_stage = self._rex["stage"].search(line)
            check_progress = self._rex["progress"].search(line)
            if check_merging is not None:
                self._increment_stage()
                self._message("Merging data", "info")
                continue
            if check_stage is not None:
                if self._stage == 0:
                    self._message("Downloading video", "info")
                elif self._stage == 1:
                    self._message("Downloading audio", "info")
                    self.data.update({ "progress": 0 })
                self._increment_stage()
                continue
            if check_progress is not None:
                data = check_progress.groupdict()
                if (p := data.get("pc", None)) is not None:
                    self._check_percentage(p, time_start)
                if (s := data.get("sp", None)) is not None:
                    self._check_speed(s)

    def _check_percentage(self, percentage, time_start):
        """Check progress of the current download

        Currently provides messages in 20-percent increments, for both video
        and audio stages.  Updates the stored progress before providing a
        message.  Modified to get the percentage in chunks of 20 regardless of
        gradual incrementation, due to tiny downloads not reaching a message
        for 100% before merging.

        @param percentage String capture for current download percentage.
        @param time_start Start time of the download, for more interesting /
        informative messages.
        """
        pc = int(percentage.split(".")[0])
        rpc = pc - (pc % 20)
        if rpc >= (self.data.get("progress") + 20):
            self.data.update({ "progress": rpc })
            tn = time.time() - time_start
            w = " " * (4 - len(str(rpc)))
            t = f"{self._get_stage()} download reached {rpc}%{w}({tn:.1f}s)"
            self._message(t, "info")

    def _check_speed(self, speed):
        """Check the speed of the current download

        If downloading at KiB/s, increment the slow count.  If exceeding the
        maximum slow count, restart the download from the current point.  If
        downloading at MiB/s, reset the slow count.

        Fragile in the sense that sometimes there can be a rapid burst of
        low-speed (KiB/s) stdout lines before lifting up to MiB/s, and
        sometimes stdout can just hang.
        TODO: Implement a timer for checking last update time of stdout.

        @param speed String capture for current download speed.
        """
        update_value = 0
        if speed.endswith("K"):
            update_value = self.data.get("slow_count") + 1
            if update_value > self.slow_count:
                self._restart(cause=0x2510)
                return
        self.data.update({ "slow_count": update_value })

    def _close_mq(self):
        """Join the message queue and message thread"""
        self._running = False
        self._q_msg.join()
        self._t_msg.join()

    def _decrement_stage(self):
        """Decrement the stage flag

        Throws a RuntimeError if `_stage` is 0 (or somehow less), for debug.
        """
        if self._stage > 0:
            self._stage -= 1
            return
        raise RuntimeError(f"DEBUG: {self._stage}")

    def _fun_t_msg(self):
        """Message queue thread function

        Times out at 0.2s and begins again if no message.  Timeout is used to
        reduce the thread's processor load.  Relies on the `_running` attr to
        stop the loop.
        """
        while self._running:
            try:
                task = self._q_msg.get(timeout=0.2)
                self._print(Message(task[0], form=task[1]))
                self._q_msg.task_done()
            except queue.Empty:
                pass

    def _get_stage(self):
        """Get the text for the current stored stage of the download

        Altered to use numeric stage flag.
        """
        if self._stage == 1:
            return "Video"
        if self._stage == 2:
            return "Audio"
        raise RuntimeError(f"DEBUG: {self._stage}")

    def _increment_stage(self):
        """Increment the stage flag"""
        self._stage += 1

    def _init_mq(self):
        """Initialise the message queue and message thread

        Initialises recursive lock, message queue, and message thread.  Starts
        the message thread immediately.
        """
        self._running = True
        self._lock = threading.RLock()
        self._q_msg = queue.Queue()
        self._t_msg = threading.Thread(
            target=self._fun_t_msg,
            daemon=True)
        self._t_msg.start()

    def _join_threads(self):
        """Join the stdout- and stderr-check threads"""
        self._stdout_thread.join()
        self._stderr_thread.join()

    def _message(self, t, f):
        """Put a message on the message queue

        Uses my Message class, so needs both text and message form.

        @param t Message text.
        @param f Message form.
        """
        self._lock.acquire()
        try:
            self._q_msg.put((f"{self._id}: {t}", f))
        finally:
            self._lock.release()

    def _new_process(self):
        """Start a new subprocess

        Also initialises and starts stdout- and stderr-check threads.  Uses
        `_build_cmd` to provide the args to `subprocess.Popen`.
        """
        self._proc = subprocess.Popen(
            self._build_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self._stdout_thread = threading.Thread(
            target=self._check_line_stdout,
            args=(self._proc.stdout, self._time_start),
            daemon=True)
        self._stderr_thread = threading.Thread(
            target=self._check_line_stderr,
            args=(self._proc.stderr,),
            daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _print(self, m):
        """Print a message to stdout

        Uses a recursive lock to avoid smashing messages together.

        @param m Message to print, of class Message (my own class).
        """
        self._lock.acquire()
        try:
            m.print()
        finally:
            self._lock.release()

    def _restart(self, cause=0x2510):
        """Kill and restart the subprocess

        Kills the process and checks the restart count.  If exceeding the max.
        number of restarts, switches `_ok` and `_restart`and returns.
        Otherwise, provides a warning to the user, depending on reason for
        restart.

        @param cause Internal code representing the cause of the restart, to
        provide more meaningful warnings.
        """
        self._proc.kill()
        rsc = self.data.get("restart_count") + 1
        if rsc > self.restart_count:
            self._ok = False
            self._restart = False
            self._message("Restart limit reached", "warn")
            return
        if cause == 0x2510:
            t = " ".join((
                "Reached slow speed limit, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            self._message(t, "warn")
        elif cause == 0x0403:
            t = " ".join((
                f"Received HTTP Error 403, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            self._message(t, "warn")
        self.data.update({ "restart_count": rsc, "slow_count": 0 })
        self._decrement_stage()

    def _store_data(self, video_id):
        """Initialise data store

        Stores video ID, and initialises a more general data hash, containing
        progress, restart count, and slow count.

        @param video_id ID of the video to download.
        """
        self._id = video_id
        self.data = {
            "id": video_id,
            "progress": 0,
            "restart_count": 0,
            "slow_count": 0,
        }

    def _wait(self):
        """Wait for the process to end

        Joins stdout and stderr threads.  Checks exit status, and stops the
        operations loop if the download and merge was successful.
        """
        self._proc.wait()
        self._join_threads()
        if self._proc.returncode == 0:
            self._restart = False


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    sp_runner = YtdlSubprocessRunner(sys.argv[1])
    sp_runner.run()
