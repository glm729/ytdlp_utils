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

from message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlSubprocessRunner:

    _rex = {
        "link": None,
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

    def __init__(self, links=tuple(), restart_count=10):
        self._store_data(links)
        self.restart_count = restart_count

    # ---- Private methods ----

    def _store_data(self, links):
        self.data = []
        for link in links:
            if (d := self._store_data_ifn(link)) is not None:
                self.data.append(d)

    def _store_data_ifn(self, link):
        return {
            "uri": link
        }

    def _build_cmd(self, idx):
        return (
            "youtube-dl",
            "--force-ipv4",
            "--geo-bypass",
            "--newline",
            "--format",
            self._opt.get("format"),
            "--output",
            self._opt.get("output"),
            self.links[idx])

    def _check_line(self, idx, line):
        search_result = self._rex.get("progress").search(line)
        if search_result is None:
            return
        data = search_result.groupdict()
        if (p := data.get("pc", None)) is not None:
            self._check_percentage(idx, p)
        if (s := data.get("sp", None)) is not None:
            self._check_speed(idx, s)

    def _check_percentage(self, idx, percentage):
        t = f"Video {idx} reached {percentage}%"
        Message(t, form="info").print()

    def _check_speed(self, speed):
        pass


# Testing
# -----------------------------------------------------------------------------


import subprocess


uri = "gzBu6vRzfKw"

out = "%(uploader)s/%(title)s.%(ext)s"

fmt = "/".join((
    "298+bestaudio",
    "136+bestaudio",
    "22",
    "bestvideo[height=720][fps=60]+bestaudio",
    "bestvideo[height=720][fps=30]+bestaudio",
    "bestvideo[height<=480]+bestaudio"))

cmd = (
    "youtube-dl",
    "--force-ipv4",
    "--geo-bypass",
    "--format",
    fmt,
    "--output",
    out,
    "--newline",
    uri)


if __name__ == "__main__":
    print(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print(f"{line.decode().strip()}\n", end='')
    print("Done")
