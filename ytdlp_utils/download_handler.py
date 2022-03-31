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
    prefix = "\033[33m?\033[m"
    body = "\033[30mPending\033[m"
    output = []
    for vid in video_ids:
        header = "\033[35m{t}\033[m".format(t=vid.ljust(pw, " "))
        output.append({
            "status": Status(prefix, header, body),
            "video": Video(),
        })
    return output


# Class definitions
# -----------------------------------------------------------------------------


class Status:
    """
    """

    def __init__(self, prefix: str, header: str, body: str):
        self.update({
            "prefix": prefix,
            "header": header,
            "body": body,
        })

    def _build(self) -> None:
        """
        """
        self.status = "{p} {h} {b}".format(
            p=self.prefix,
            h=self.header,
            b=self.body)

    def update(self, data: dict) -> None:
        """
        """
        for (k, v) in data.items():
            if not k in ["prefix", "header", "body"]:
                continue
            setattr(self, k, v)
        self._build()


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


class DHMessageThread(threading.Thread):

    def __init__(self, lock, screen, message_queue):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.lock = lock
        self.screen = screen
        self.message_queue = message_queue

    def handle_message(self, task: dict) -> None:
        """Handle an incoming message using the given dataset

        @param task Message data, containing message text and (optionally)
        message index
        """
        method = "add_line"
        if (idx := task.get("idx", None)) is not None:
            if idx < len(self.screen.content):
                method = "replace_line"
        with self.lock:
            getattr(self.screen, method)(**task)
            self.screen.flush()

    def run(self) -> None:
        """Run the message thread operations

        Handles getting tasks from the queue and passing to the message handler
        method.
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.message_queue.get(timeout=0.2)
                self.handle_message(task)
                self.message_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self) -> None:
        """Stop the message thread operations"""
        self._stopevent.set()


class DHTaskProcess(multiprocessing.Process):

    def __init__(self, task_queue, message_queue):
        super().__init__(daemon=True)
        self._stopevent = multiprocessing.Event()
        self.task_queue = task_queue
        self.message_queue = message_queue

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of message data
        """
        self.message_queue.put(data)

    def process(self, task: dict) -> None:
        """
        """
        task.get("status").update({ "body": "Doing a thing", })
        self.message({
            "idx": task.get("idx"),
            "text": task.get("status").status,
        })
        time.sleep(random.random() * 4.0)
        task.get("status").update({ "body": "Thing done", })
        self.message({
            "idx": task.get("idx"),
            "text": task.get("status").status,
        })

    def run(self) -> None:
        """Run task thread operations

        Effectively a handler to loop for collecting tasks and running the
        class `process` method.
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.task_queue.get(timeout=0.2)
                self.process(task)
                self.task_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self) -> None:
        """Stop the task handler operations"""
        self._stopevent.set()


class DownloadHandler:
    """
    """

    # TODO
    ytdlp_options = {
        "format": "bestvideo[height<=720][fps<=60]+bestaudio",
        "outtmpl": "TESTING/%(uploader)s__%(title)s__%(id)s.%(ext)s",
    }

    def __init__(self, video_ids: list, processes: int = 1):
        self.lock = threading.Lock()
        self.screen = Overwriteable()
        self.message_queue = multiprocessing.JoinableQueue()
        self.message_thread = DHMessageThread(
            self.lock,
            self.screen,
            self.message_queue)
        self.videos = store_video_data(video_ids)
        self.processes = processes

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of data for the message handler
        """
        self.message_queue.put(data)

    def run(self) -> None:
        """Run the multipush handler operations

        Starts the message handler.  Exits early if no branches are provided.
        Fills task queue and prepares task threads.  Starts task threads and
        marks all for stopping on an empty queue.  Joins the task queue to wait
        until all tasks are complete.  Joins the task threads.  Stops the
        instance message handlers.
        """
        self.message_thread.start()
        l = len(self.videos)
        if l == 0:
            self.message({ "idx": 0, "text": "No video IDs provided", })
            self.stop()
            return
        s = "" if l == 1 else "s"
        self.message({
            "idx": 0,
            "text": f"\033[1;32m✓\033[m Downloading {l} video{s}",
        })
        task_queue = multiprocessing.JoinableQueue()
        for (idx, vid) in enumerate(self.videos):
            vid.update({ "idx": idx + 1, })  # Hardcoded offset
            task_queue.put(vid)
            self.message({
                "idx": vid.get("idx"),
                "text": vid.get("status").status,
            })
        workers = []
        for _ in range(0, self.processes):
            workers.append(
                DHTaskProcess(
                    task_queue,
                    self.message_queue))
        for w in workers:
            w.start()
        for w in workers:
            w.stop()
        task_queue.join()
        for w in workers:
            w.join()
        self.stop()

    def stop(self) -> None:
        """Stop the instance message handlers"""
        self.message_queue.join()
        self.message_thread.stop()
        self.message_thread.join()


# Main function
# -----------------------------------------------------------------------------


def main():
    dh = DownloadHandler(
        [
            "BpgGXvw-ZLE",
            "1IDfoTxFNg0",
            "YikfKLxfRYI",
        ],
        processes=2)
    dh.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
