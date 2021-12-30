#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import time

from _modules.message import Message
from text_link_parser import TextLinkParser
from subprocess_runner import SubprocessRunner


# Class definition
# -----------------------------------------------------------------------------


class MultiprocessRunner:

    def __init__(self, path=None, ncore=None):
        self.q_task = multiprocessing.JoinableQueue()
        self._set_ncore(ncore)
        if path is not None:
            self.read_file(path)  # Assuming text for now

    # ---- Public methods

    def read_file(self, path: str) -> None:
        """Read and parse a text file containing video links

        Currently assumes text format only.

        @param path File path for the file to read and parse.
        """
        data = TextLinkParser(path=path)
        if len(v := data.video_ids) > 0:
            s = '' if len(v) == 1 else "s"
            t = f"Found {len(v)} video ID{s}"
            Message(t, form="ok").print()
            self.video_ids = v
            return
        raise RuntimeError("No video IDs found")

    def run(self) -> None:
        """Run all video downloads

        Records time to complete operations for more interesting messages.
        Enqueues all tasks, generates and starts all processes, and joins the
        job queue.
        """
        time_start = time.time()
        for video_id in self.video_ids:
            self.q_task.put(video_id)
        _procs = []
        for _ in range(0, self._ncore):
            _procs.append(
                multiprocessing.Process(
                    target=self._target_process,
                    daemon=True))
        for p in _procs:
            p.start()
        for p in _procs:
            p.join()
        self.q_task.join()
        time_end = time.time() - time_start
        s = '' if len(self.video_ids) == 1 else "s"
        t = f"Video{s} downloaded in {time_end:.1f}s"
        Message(t, form="ok").print()

    # ---- Private methods

    def _target_process(self) -> None:
        """Multiprocessing operations target function"""
        while True:
            if self.q_task.empty():
                return
            video_id = self.q_task.get()
            sp_runner = SubprocessRunner(video_id)
            sp_runner.run()
            self.q_task.task_done()

    def _set_ncore(self, ncore: int) -> None:
        """Set the number of CPU cores to use for operations

        @param ncore Maximum number of cores to use, if wanting to restrict.
        """
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
    runner = MultiprocessRunner(sys.argv[1])
    runner.run()
