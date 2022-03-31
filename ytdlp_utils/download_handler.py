#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import queue
import random
import threading
import time

from overwriteable import Overwriteable
from status_line import StatusLine


# Function definitions
# -----------------------------------------------------------------------------


def store_video_data(video_ids) -> list:
    """Prepare a default set of data for each video ID

    - Produce list of output data:
      - { "video": Video(), "status": StatusLine(...), }
    - Mutate data later with attr `idx`:
      - task.update({ "idx": i + 1, })

    @param video_ids List or tuple of video IDs to store
    @return List of dicts; Video and StatusLine per video ID provided
    """
    pw = max(map(len, video_ids))
    output = []
    for video_id in video_ids:
        data = {
            "main": f"\033[35m{video_id}\033[m",
            "prefix": "\033[33m?\033[m",
            "suffix": "\033[30mPending\033[m",
            "pw": pw,
        }
        output.append({ "video": Video(), "status": StatusLine(**data), })
    return output


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
        while True:
            try:
                task = self.task_queue.get(block=False)
                # TODO ---- Dummy ops for now, for testing
                task.get("status").set_suffix("Doing a thing")
                self.message({
                    "idx": task.get("idx"),
                    "text": task.get("status").text,
                })
                time.sleep(random.random() * 5.0)
                task.get("status").set_suffix("Thing done")
                self.message({
                    "idx": task.get("idx"),
                    "text": task.get("status").text,
                })
                self.task_queue.task_done()
            except queue.Empty:
                break


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
        "outtmpl": "TESTING/%(uploader)s__%(title)s__%(id)s.%(ext)s",
    }

    def __init__(self, video_ids: list, n_procs: int = 1):
        self.lock = multiprocessing.Lock()
        self.screen = Overwriteable()
        (self.message_pipe_r, self.message_pipe_s) = multiprocessing.Pipe()
        self.message_thread = DHMessageThread(
            self.lock,
            self.screen,
            self.message_pipe_r)
        self.n_procs = n_procs
        self.video_data = store_video_data(video_ids)

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
            v.update({ "idx": i + 1, })  # Hardcoded line offset
            task_queue.put(v)
            self.message({
                "idx": v.get("idx"),
                "text": v.get("status").text,
            })
        # result_thread = DHResultThread(result_queue)
        task_processes = []
        for _ in range(0, self.n_procs):
            task_processes.append(
                DHTaskProcess(
                    self.lock,
                    task_queue,
                    self.message_pipe_s,
                    self.ytdlp_options.copy()))
        for t in task_processes:
            t.start()
        task_queue.join()  # Unblock when all tasks are done
        for t in task_processes:
            t.join(0)  # Hard join -- no more tasks at this stage
        # result_thread.join()
        # result = result_thread.result
        self.message({
            "idx": len(self.video_data) + 1,  # Hardcoded line offset
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
    dh = DownloadHandler([
        "BpgGXvw-ZLE",
        "1IDfoTxFNg0",
        "YikfKLxfRYI",
    ])
    dh.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
