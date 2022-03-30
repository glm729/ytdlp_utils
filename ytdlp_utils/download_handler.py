#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import queue
import random
import threading
import time

from overwriteable import Overwriteable


# Function definitions
# -----------------------------------------------------------------------------





# Class definitions
# -----------------------------------------------------------------------------


class Video:
    """Class to collect and handle data for each video download

    Needs to be able to store required info about the video itself, download
    stage, download completion, and possibly additional info such as what index
    it is at in the screen content to push an update, or some other unique
    identifier such as that.
    """

    _stage = {
        0: "Video",
        1: "Audio",
    }

    def __init__(self):
        self.progress = {
            0: 0.0,
            1: 0.0,
        }

    def set_progress(self, percentage: float) -> None:
        """Set the progress for the current download stage

        Updates the progress according to the current download stage.

        @param percentage Percentage completion of the current download
        """
        self.progress.update({ self.stage: percentage, })

    def set_stage(self, stage: int) -> None:
        """Set the video download stage

        Stage must only be 0 or 1 -- video or audio.

        @param stage Download stage: 0 == video, 1 == audio
        """
        if not stage in [0, 1]:
            raise RuntimeError("Stage must only be 0 or 1")
        self.stage = stage


class Logger:
    """Custom logger definition for yt_dlp.YoutubeDL

    Sinks most messages, and updates status of the instance video.
    """

    def __init__(self, video: Video):
        self.video = video

    def debug(self, m: str) -> None:
        """
        """
        pass

    def info(self, m: str) -> None:
        """
        """
        pass


class DHTaskProcess(multiprocessing.Process):

    def __init__(
            self,
            lock: multiprocessing.Lock,
            task_queue: multiprocessing.JoinableQueue,
            message_pipe,
            ytdlp_options: dict):
        super().__init__(daemon=True)
        self._stopevent = multiprocessing.Event()
        self.lock = lock
        self.task_queue = task_queue
        self.message_pipe = message_pipe
        self.ytdlp_options = ytdlp_options

    def message(self, data: dict) -> None:
        """
        """
        with self.lock:
            self.message_pipe.send(data)

    def run(self) -> None:
        """
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.task_queue.get(timeout=0.2)
                # TODO ---- Dummy ops for now, for testing
                self.message({
                    "idx": task.get("idx"),
                    "text": "Doing a thing: {t}".format(t=task.get("task")),
                })
                time.sleep(random.random() * 5.0)
                self.message({
                    "idx": task.get("idx"),
                    "text": "Thing done: {t}".format(t=task.get("task")),
                })
                self.task_queue.task_done()
            except queue.Empty:
                break

    def stop(self) -> None:
        """Stop the task process operations"""
        self._stopevent.set()


class DHResultThread(threading.Thread):

    def __init__(self, result_queue):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.result = []
        self.result_queue = result_queue

    def run(self) -> None:
        """
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                result = self.result_queue.get(timeout=0.2)
                self.result.append(result)
                self.result_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self) -> None:
        """Stop the result thread operations"""
        self._stopevent.set()


class DHMessageThread(threading.Thread):

    def __init__(
            self,
            lock: multiprocessing.Lock,
            screen: Overwriteable,
            message_pipe):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.lock = lock
        self.screen = screen
        self.message_pipe = message_pipe

    def handle_message(self, task: dict) -> None:
        """Handle an incoming message from the message queue

        @param task Task data pulled from the message queue
        """
        m = "add_line"
        if (idx := task.get("idx", None)) is not None:
            if idx < len(self.screen.content):
                m = "replace_line"
        with self.lock:
            getattr(self.screen, m)(**task)
            self.screen.flush()

    def run(self) -> None:
        """
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            if self.message_pipe.poll(timeout=0.2):
                with self.lock:
                    text = self.message_pipe.recv()
                self.handle_message(text)
            if self._stopevent.is_set():
                break

    def stop(self) -> None:
        """Stop the message thread operations"""
        self._stopevent.set()


class DownloadHandler:
    """
    """

    # TODO
    ytdlp_options = {
        "format": "bestvideo[height<=720][fps<=60]+bestaudio",
        "outtmpl": "TESTING/%(uploader)s__%(title)%s.%(ext)s",
    }

    def __init__(self, video_data: list):
        self.lock = multiprocessing.Lock()
        self.screen = Overwriteable()
        (self.message_pipe_r, self.message_pipe_s) = multiprocessing.Pipe()
        self.message_thread = DHMessageThread(
            self.lock,
            self.screen,
            self.message_pipe_r)
        self.video_data = video_data

    def message(self, data: dict) -> None:
        """Send a message via the instance message pipe

        @param data Dict of data for the message; `text` and, optionally, `idx`
        """
        with self.lock:
            self.message_pipe_s.send(data)

    def run(self) -> None:
        """
        """
        self.message_thread.start()
        l = len(self.video_data)
        if l == 0:
            self.message({
                "idx": 0,
                "text": "No video data provided",
            })
            self.stop()
            return
        s = "" if l == 1 else "s"
        self.message({
            "idx": 0,
            "text": f"Received {l} video ID{s}",
        })
        task_queue = multiprocessing.JoinableQueue()
        result_queue = multiprocessing.JoinableQueue()
        for (i, v) in enumerate(self.video_data):
            task_queue.put({ "idx": i + 1, "task": v, })
            self.message({
                "idx": i + 1,
                "text": f"{v}: Pending",
            })
        self.result_thread = DHResultThread(result_queue)
        task_processes = []
        for i in range(0, 2):  # TODO: Un-hardcode this
            task_processes.append(
                DHTaskProcess(
                    self.lock,
                    task_queue,
                    self.message_pipe_s,
                    self.ytdlp_options.copy()))
        for t in task_processes:
            t.start()
        for t in task_processes:
            t.join()
        self.message({
            "idx": len(self.video_data) + 1,
            "text": "Operations complete",
        })
        self.stop()

    def stop(self) -> None:
        """Stop the instance message handlers"""
        self.message_thread.stop()
        self.message_thread.join()
        self.message_pipe_r.close()
        self.message_pipe_s.close()


# Main function
# -----------------------------------------------------------------------------


def main():
    dh = DownloadHandler([1, 2, 3, 4, 5, 6, 7])
    dh.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
