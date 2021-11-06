#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import time

from _modules.message import Message
from ytdl_text_link_parser import YtdlTextLinkParser
from ytdl_subprocess_runner import YtdlSubprocessRunner


# Class definition
# -----------------------------------------------------------------------------


class YtdlMultiprocessRunner:

    def __init__(self, path=None, ncore=None):
        self.q = multiprocessing.JoinableQueue()
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
        time_start = time.time()
        for video_id in self.video_ids:
            self.q.put(video_id)
        _procs = []
        for _ in range(0, self._ncore):
            p = multiprocessing.Process(target=self._target, daemon=True)
            _procs.append(p)
        for p in _procs:
            p.start()
        for p in _procs:
            p.join()
        self.q.join()
        time_end = time.time() - time_start
        s = '' if len(self.video_ids) == 1 else "s"
        t = f"Video{s} downloaded in {time_end:.1f}s"
        Message(t, form="ok").print()

    # ---- Private methods

    def _target(self):
        while True:
            if self.q.empty():
                return
            video_id = self.q.get()
            sp_runner = YtdlSubprocessRunner(video_id)
            sp_runner.run()
            self.q.task_done()

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
