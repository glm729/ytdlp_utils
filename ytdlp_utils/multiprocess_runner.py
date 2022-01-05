#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import time

from queue import Empty

from message_handler import MessageHandler
from subprocess_runner import SubprocessRunner
from text_link_parser import TextLinkParser


# Class definition
# -----------------------------------------------------------------------------


class MultiprocessRunner:

    def __init__(self, path=None, ncore=None):
        self._path = path
        self._set_ncore(ncore)

    # ---- Public methods

    def run(self) -> None:
        """Run all video downloads

        Records time to complete operations for more interesting messages.
        Enqueues all tasks, generates and starts all processes, and joins the
        job queue.
        """
        self._init_message_handler()
        if not self._read_file(self._path):
            self._end_message_handler()
            return
        time_start = time.time()
        q_task = multiprocessing.JoinableQueue()
        for v in self.video_data:
            q_task.put(v)
        procs = []
        for _ in range(self._ncore):
            procs.append(
                multiprocessing.Process(
                    target=self._fun_process,
                    args=(q_task,),
                    daemon=True))
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        q_task.join()
        time_end = time.time() - time_start
        s = '' if len(self.video_data) == 1 else "s"
        self._message(f"Video{s} downloaded in {time_end:.1f}s", "ok")
        self._end_message_handler()

    # ---- Private methods

    def _end_message_handler(self) -> None:
        """End the instance message handler"""
        self._message_handler.end()

    def _fun_process(self, q_task: multiprocessing.JoinableQueue) -> None:
        """Multiprocessing operations target function

        @param q_task Task queue, from which to get tasks.
        """
        while True:
            try:
                video_data = q_task.get(block=False)
                sp_runner = SubprocessRunner(**video_data)
                sp_runner.run()
                q_task.task_done()
            except Empty:
                break

    def _init_message_handler(self) -> None:
        """Initialise the instance message handler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text: str, form: str) -> None:
        """Print a message via the message handler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _read_file(self, path: str) -> None:
        """Read and parse a text file containing video links

        Currently assumes text format only.

        @param path File path for the file to read and parse.
        """
        data = TextLinkParser(path=path)
        if (l := len(v := data.video_ids)) > 0:
            s = '' if l == 1 else "s"
            self._message(f"Found {l} video ID{s}", "ok")
            self._store_video_data(v)
            return True
        self._message("No video IDs found", "warn")
        return False

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
            self._message(t, "warn")
        self._ncore = nc

    def _store_video_data(self, video_ids: list) -> None:
        """Store the video ID data in the instance

        Provides colouring for the video ID prefix.

        @param video_ids Array of video IDs to store.
        """
        colour_index = 30
        self.video_data = []
        for vid in video_ids:
            self.video_data.append({
                "video_id": vid,
                "colour_index": colour_index
            })
            if colour_index == 37:
                colour_index -= 7
                continue
            colour_index += 1


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    runner = MultiprocessRunner(sys.argv[1])
    runner.run()
