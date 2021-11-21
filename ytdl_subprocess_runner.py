#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


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

    _rex = {
        "merging": re.compile(r"^\[Merger\] Merging formats into"),
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s"))),
        "stage": re.compile(r"^\[download\] Destination:")
    }

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

    def __init__(self, video_id, slow_count=30, restart_count=10):
        self._store_data(video_id)
        self.slow_count = slow_count
        self.restart_count = restart_count

    def run(self):
        t = f"{self._id}: Starting download"
        Message(t, form="ok").print()
        self._time_start = time.time()
        while self._restart:
            self._new_process()
            self._wait()
        time_end = time.time() - self._time_start
        if self._ok:
            m = {
                "text": " ".join((
                    f"{self._id}: Video downloaded and merged",
                    f"in {time_end:.1f}s")),
                "form": "ok"
            }
        else:
            m = {
                "text": " ".join((
                    f"{self._id}: Video download failed",
                    f"after {time_end:.1f}s")),
                "form": "exit"
            }
        Message(**m).print()

    # ---- Private methods ----

    def _store_data(self, video_id):
        self._id = video_id
        self._stage = "start"
        self.data = {
            "id": video_id,
            "progress": 0,
            "restart_count": 0,
            "slow_count": 0
        }

    def _build_cmd(self):
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

    def _check_line_stdout(self, stdout, time_start):
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()
            check_merging = self._rex["merging"].search(line)
            check_stage = self._rex["stage"].search(line)
            check_progress = self._rex["progress"].search(line)
            if check_merging is not None:
                Message(f"{self._id}: Merging data", form="info").print()
                continue
            if check_stage is not None:
                if self._stage == "start":
                    self._stage = "Video"
                    t = f"{self._id}: Downloading video"
                    Message(t, form="info").print()
                elif self._stage == "Video":
                    self._stage = "Audio"
                    self.data.update({ "progress": 0 })
                    t = f"{self._id}: Downloading audio"
                    Message(t, form="info").print()
                continue
            if check_progress is not None:
                data = check_progress.groupdict()
                if (p := data.get("pc", None)) is not None:
                    self._check_percentage(p, time_start)
                if (s := data.get("sp", None)) is not None:
                    self._check_speed(s)

    def _check_line_stderr(self, stderr):
        while (l := stderr.readline()):
            line = l.decode("utf-8").strip()
            #=> DEBUG
            # t = f"\n{' ' * 7}".join(("STDERR:", line))
            # Message(t, form="warn")
            #<=
            if line.endswith("HTTP Error 403: Forbidden"):
                self._restart(cause="403")
                continue

    def _check_percentage(self, percentage, time_start):
        pc = int(percentage.split(".")[0])
        if pc >= (p := self.data.get("progress") + 20):
            self.data.update({ "progress": p })
            tn = time.time() - time_start
            w = " " * (4 - len(str(p)))
            t = " ".join((
                f"{self._id}: {self._stage} download reached",
                f"{p}%{w}({tn:.1f}s)"))
            Message(t, form="info").print()

    def _check_speed(self, speed):
        if speed.endswith("K"):
            update_value = self.data.get("slow_count") + 1
            if update_value > self.slow_count:
                self._restart(cause="slow")
                return
        else:
            update_value = 0
        self.data.update({ "slow_count": update_value })

    def _restart(self, cause="slow"):
        self._proc.kill()
        rsc = self.data.get("restart_count") + 1
        if rsc > self.restart_count:
            self._ok = False
            self._restart = False
            t = f"{self._id}: Restart limit reached"
            Message(t, form="warn").print()
            return
        if cause == "slow":
            t = " ".join((
                f"{self._id}: Reached slow speed limit, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            Message(t, form="warn").print()
        elif cause == "403":
            t = " ".join((
                f"{self._id}: Received HTTP Error 403, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            Message(t, form="warn").print()
        self.data.update({ "restart_count": rsc, "slow_count": 0 })

    def _new_process(self):
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

    def _wait(self):
        self._proc.wait()
        self._join_threads()
        if self._proc.returncode == 0:
            self._restart = False

    def _join_threads(self):
        self._stdout_thread.join()
        self._stderr_thread.join()


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    sp_runner = YtdlSubprocessRunner(sys.argv[1])
    sp_runner.run()
