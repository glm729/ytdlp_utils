#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import re
import subprocess
import time

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlSubprocessRunner:

    _ok = True

    _rex = {
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s")))
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
        time_start = time.time()
        self._new_process()
        while (l := self._proc.stdout.readline()):
            self._check_line_stdout(l.decode().strip(), time_start)
        while (l := self._proc.stderr.readline()):
            self._check_line_stderr(l.decode().strip())
        time_end = time.time() - time_start
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

    def _check_line_stdout(self, line, time_start):
        search_result = self._rex.get("progress").search(line)
        if search_result is None:
            return
        data = search_result.groupdict()
        if (p := data.get("pc", None)) is not None:
            self._check_percentage(p, time_start)
        if (s := data.get("sp", None)) is not None:
            self._check_speed(s)

    def _check_line_stderr(self, line):
        #=> DEBUG
        t = f"\n{' ' * 7}".join(("STDERR:", line))
        #<=
        if line.endswith("HTTP Error 403: Forbidden"):
            self._restart(cause="403")
            return

    def _check_percentage(self, percentage, time_start):
        pc = int(percentage.split(".")[0])
        if pc >= (p := self.data.get("progress") + 20):
            self.data.update({ "progress": p })
            tn = time.time() - time_start
            w = " " * (4 - len(str(p)))
            t = f"{self._id}: Download reached {p}%{w}({tn:.1f}s)"
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
        self._new_process()

    def _new_process(self):
        self._proc = subprocess.Popen(
            self._build_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    sp_runner = YtdlSubprocessRunner(sys.argv[1])
    sp_runner.run()
