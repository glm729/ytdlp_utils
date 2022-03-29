#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import multiprocessing
import queue
import threading

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
            task_queue: multiprocessing.JoinableQueue,
            message_queue: multiprocessing.JoinableQueue,
            ytdlp_options: dict):
        super().__init__(daemon=True)
        self._stopevent = multiprocessing.Event()
        self.task_queue = task_queue
        self.message_queue = message_queue
        self.ytdlp_options = ytdlp_options

    def run(self) -> None:
        """
        """
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.task_queue.get(timeout=0.2)
                # do
                self.task_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
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
                self.result.append(self.result_queue.get(timeout=0.2))
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
            lock: multiprocessing.RLock,
            screen: Overwriteable,
            message_queue: multiprocessing.JoinableQueue):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.lock = lock
        self.screen = screen
        self.message_queue = message_queue

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
            try:
                self.handle_message(self.message_queue.get(timeout=0.2))
                self.message_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self) -> None:
        """Stop the message thread operations"""
        self._stopevent.set()


class DownloadHandler:
    """
    """

    def __init__(self, video_data: list):
        self.lock = multiprocessing.RLock()
        self.screen = Overwriteable()
        self.message_queue = multiprocessing.JoinableQueue()
        self.message_thread = DHMessageThread(
            self.lock,
            self.screen,
            self.message_queue)
        self.video_data = video_data

    def run(self) -> None:
        """
        """
        self.message_thread.start()
        l = len(self.video_data)
        if l == 0:
            self.message_queue.put({
                "idx": 0,
                "text": "No video data provided",
            })
            self.message_thread.stop()
            self.message_queue.join()
            self.message_thread.join()
            return


# Main function
# -----------------------------------------------------------------------------


def main():
    dh = DownloadHandler([])
    dh.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
