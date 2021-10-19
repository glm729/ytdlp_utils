#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing

from _modules.message import Message
from ytdl_text_link_parser import YtdlTextLinkParser
from ytdl_subprocess_runner import YtdlSubprocessRunner


# Class definition
# -----------------------------------------------------------------------------


class YtdlMultiprocessRunner:

    def __init__(self, path=None, ncore=None):
        self._set_ncore(ncore)
        if path is not None:
            self.read_file(path)  # Assuming text for now

    # ---- Public methods

    def read_file(self, path):
        data = YtdlTextLinkParser(path=path)
        if len((v := data.video_ids)) > 0:
            s = '' if len(v) == 1 else "s"
            t = f"Found {len(v)} video ID{s}"
            Message(t, form="ok").print()
            self.video_ids = v
            return
        raise RuntimeError("No video IDs found")

    def run(self):
        with multiprocessing.Pool(self._ncore) as worker_pool:
            worker_pool.map(self._run, self.video_ids)

    # ---- Private methods

    def _run(self, video_id):
        sp_runner = YtdlSubprocessRunner(video_id)
        sp_runner.run()

    def _set_ncore(self, ncore):
        nc = multiprocessing.cpu_count() - 2
        if nc < 1:
            self._ncore = 1
            return
        if ncore:
            if ncore <= nc:
                self._ncore = ncore
                return
            t = ", ".join((
                f"Specified number of cores ({ncore}) is too high",
                f"limiting to {nc}"))
            Message(t, form="warn").print()
        self._ncore = nc


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    runner = YtdlMultiprocessRunner(sys.argv[1])
    runner.run()
