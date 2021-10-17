#!/usr/bin/env python3.8


# TODO:
# - Parse content of most recent line to get speed
# - Increment count of lines below expected speed
# - Restart run if count exceeds number
#   - Capture process within attr, class, etc.
#   - Kill and re-run when necessary


# Module imports
# -----------------------------------------------------------------------------


import re
import subprocess

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlSubprocessRunner:

    _rex = {
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at ",
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

    def __init__(self, video_id, slow_count=10, restart_count=10):
        self._store_data(video_id)
        self.slow_count = slow_count
        self.restart_count = restart_count

    def run(self):
        t = "Starting new process"
        Message(t, form="ok").print()
        self._new_process()
        while True:
            line = self._proc.stdout.readline()
            if not line:
                break
            self._check_line(line.decode().strip())

    # ---- Private methods ----

    def _store_data(self, video_id):
        self.data = {
            "id": video_id,
            "progress": 0,
            "restart_count": 0,
            "slow_count": 0
        }

    def _build_cmd(self):
        return (
            "youtube-dl",
            "--force-ipv4",
            "--geo-bypass",
            "--newline",
            "--format",
            self._opt.get("format"),
            "--output",
            self._opt.get("output"),
            self.data.get("id"))

    def _check_line(self, line):
        search_result = self._rex.get("progress").search(line)
        if search_result is None:
            return
        data = search_result.groupdict()
        if (p := data.get("pc", None)) is not None:
            self._check_percentage(p)
        if (s := data.get("sp", None)) is not None:
            self._check_speed(s)

    def _check_percentage(self, percentage):
        pc = int(percentage.split(".")[0])
        if pc >= (p := self.data.get("progress") + 20):
            self.data.update({ "progress": p })
            t = f"Download reached {p}%"
            Message(t, form="info").print()

    def _check_speed(self, speed):
        if speed.endswith("K"):
            update_value = self.data.get("slow_count") + 1
            if update_value > self.slow_count:
                self._restart()
                return
        else:
            update_value = 0
        self.data.update({ "slow_count": update_value })

    def _restart(self):
        self._proc.kill()
        rsc = self.data.get("restart_count") + 1
        if rsc > self.restart_count:
            t = "Reached restart limit"
            Message(t, form="exit").print()
            return
        t = " ".join((
            "Slow speed limit reached, restarting download",
            f"(restarts remaining: {self.restart_count - rsc})"))
        Message(t, form="warn").print()
        self.data.update({ "restart_count": rsc, "slow_count": 0 })
        self._new_process()

    def _new_process(self):
        self._proc = subprocess.Popen(
            self._build_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)


# Testing
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    uri = "gzBu6vRzfKw"
    sp_runner = YtdlSubprocessRunner(uri)
    sp_runner.run()
