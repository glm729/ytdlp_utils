#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import argparse
import queue
import re
import sys
import threading
import time
import yt_dlp

from overwriteable import Overwriteable
from status import Status
from video import Video


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
            "status": Status({
                "prefix": prefix,
                "header": header,
                "body": body,
            }),
            "video": Video(vid),
        })
    return output


# Auxiliary class definitions
# -----------------------------------------------------------------------------


class ProgressHook:

    def __init__(self, task, message_queue):
        self._last_update = time.time()
        self.task = task
        self.message_queue = message_queue

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Message data
        """
        self.message_queue.put(data)

    def check_percentage(self, num, den) -> None:
        """Check the percentage of the current download

        If more than ~1/3 of a second since last update, update the status and
        screen contents.

        @param num Numerator; current downloaded bytes
        @param den Denominator; total downloadable bytes
        """
        pc = round((num / den) * 100, 1)
        self.task.get("video").set_progress(pc)
        if time.time() > (self._last_update + 0.333):
            self.task.get("status").update({
                "body": "Downloading {s} ({p}%)".format(
                    s=self.task.get("video").get_stage_text(lower=True),
                    p=str(pc).rjust(5, " ")),
            })
            self.update_status(self.task)
        self._last_update = time.time()

    def downloading(self, data: dict) -> None:
        """Progress hook callback for "downloading" stage

        @param data Dict of data sent by yt_dlp.YoutubeDL
        """
        if not data.get("status") == "downloading":
            return
        if data.get("info_dict").get("fragments", None) is not None:
            if not self.task.get("video").dash_notified:
                self.task.get("status").update({
                    "suffix": "\033[33m[!] DASH video\033[m",
                })
                self.update_status(self.task)
                self.task.get("video").dash_notified = True
            num = data.get("fragment_index")
            den = data.get("fargment_count")
        else:
            num = data.get("downloaded_bytes")
            den = data.get("total_bytes")
        self.check_percentage(num, den)

    def update_status(self, task) -> None:
        """Send the updated task status via the instance message queue

        @param task Task for which to update the status line
        """
        self.message({
            "idx": task.get("idx"),
            "text": task.get("status").status,
        })


class Logger:
    """Custom logger definition for yt_dlp.YoutubeDL

    Skips most messages, and updates status of the instance video.
    """

    _download_failure = "".join((
        "[download] Got server HTTP error: ",
        "<urlopen error timed out>"))

    _rex_retry = re.compile(r"Retrying \(attempt (?P<n>\d+) of (?P<m>\d+)\)")

    _skip_hints = (
        "[dashsegments]",
        "[info]",
        "[youtube]",
        "Deleting original file")

    _warn_mkv = "".join((
        "Requested formats are incompatible for merge ",
        "and will be merged into mkv"))

    def __init__(self, task: dict, message_queue: queue.Queue):
        self.task = task
        self.message_queue = message_queue
        self._status_last_update = time.time()
        # DEBUG ----
        self._count = {
            "debug": 0,
            "error": 0,
            "info": 0,
            "warning": 0,
        }

    def _message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of data for the message
        """
        self.message_queue.put(data)

    def _update(self) -> None:
        """Send an update of the current status via the message queue"""
        self._message({
            "idx": self.task.get("idx"),
            "text": self.task.get("status").status,
        })

    def debug(self, m: str) -> None:
        """Log debug messages

        Changes text if already downloaded, merging, or changing stage.

        @param m Message text
        """
        if any(map(lambda x: m.startswith(x), self._skip_hints)):
            return
        if m.endswith("has already been downloaded"):
            self.task.get("video").already_downloaded = True
            self.task.get("status").update({
                "prefix": "\033[1;32m✓\033[m",
                "body": "\033[32mAlready downloaded\033[m",
            })
            self._update()
            return
        if m.startswith("[Merger]"):
            self.task.get("status").update({
                "body": "\033[36mMerging data\033[m",
            })
            self._update()
            return
        if m.startswith("[download]"):
            if m.startswith("[download] Destination:"):
                v = self.task.get("video")
                # If stage not yet set, set to video and notify
                if v.stage is None:
                    v.set_stage(0)
                # If video, switch to audio
                elif v.stage == 0:
                    v.set_stage(1)
                # Update the status with the current download stage
                self.task.get("status").update({
                    "body": "Downloading {s}".format(
                        s=v.get_stage_text(lower=True)),
                })
                self._update()
                return
        if (match := self._rex_retry.search(m)) is not None:
            group = match.groupdict()
            self.task.get("status").update({
                "suffix": "\033[33m[!] Retry {n} / {m}\033[m".format(
                    n=group.get("n").rjust(len(group.get("m"))),
                    m=group.get("m")),
            })
            self._update()
            return
        if m == self._download_failure:
            self.task.get("status").update({
                "prefix": "\033[1;31m✘\033[m",
                "body": "\033[31mFailed to download\033[m",
            })
            self._update()
            return

    def error(self, m: str) -> None:
        """Log error messages

        @param m Message text
        """
        self._count.update({ "error": self._count.get("error") + 1, })
        self.task.get("status").update({
            "body": "Received error message {n}".format(
                n=self._count.get("error")),
        })
        self._update()

    def info(self, m: str) -> None:
        """Log info messages

        @param m Message text
        """
        self._count.update({ "info": self._count.get("info") + 1, })
        self.task.get("status").update({
            "body": "Received info message {n}".format(
                n=self._count.get("info")),
        })
        self._update()

    def warning(self, m: str) -> None:
        """Log warning messages

        Skips the MKV merge message.

        @param m Message text
        """
        if m == self._warn_mkv:
            return
        self._count.update({ "warning": self._count.get("warning") + 1, })
        self.task.get("status").update({
            "body": "Received warning message {n}".format(
                n=self._count.get("warning")),
        })
        self._update()


# DownloadHandler class definitions
# -----------------------------------------------------------------------------


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


class DHTaskThread(threading.Thread):

    def __init__(self, task_queue, message_queue):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.task_queue = task_queue
        self.message_queue = message_queue

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of message data
        """
        self.message_queue.put(data)

    def process(self, task: dict) -> None:
        """Process the current video download

        @param task Dict of data for the current task
        """
        task.get("status").update({
            "prefix": "\033[1;33m?\033[m",
            "body": "Starting",
        })
        self.update_status(task)

        progress_hook = ProgressHook(task, self.message_queue)

        task.get("ytdlp_options").update({
            "logger": Logger(task, self.message_queue),
            "progress_hooks": [
                progress_hook.downloading,
            ],
        })

        time_start = time.time()

        try:
            with yt_dlp.YoutubeDL(task.get("ytdlp_options")) as yt:
                yt.download((task.get("video").id,))
        except yt_dlp.utils.DownloadError:
            task.get("status").update({
                "prefix": "\033[1;31m✘\033[m",
                "body": "\033[31mFailed to download\033[m",
            })
            self.update_status(task)

        time_end = time.time()

        if task.get("video").already_downloaded:
            return

        task.get("status").update({
            "prefix": "\033[1;32m✓\033[m",
            "body": "\033[32mDownloaded and merged\033[m in {t}s".format(
                t=round(time_end - time_start, 1)),
        })
        self.update_status(task)

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

    def update_status(self, task) -> None:
        """Send the updated task status via the instance message queue

        @param task Task for which to update the status line
        """
        self.message({
            "idx": task.get("idx"),
            "text": task.get("status").status,
        })


class DownloadHandler:
    """Handle batch-downloading of Youtube videos, using yt-dlp

    Reworked to use multiple threads and dynamic stdout content.

    TODO: Exception handling, e.g. TimeoutError
    """

    ytdlp_options = {
        "format": "/".join((
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "merge_output_format": "mkv",
        "outtmpl": "%(uploader)s/%(title)s.%(ext)s",
        "retries": 99,
    }

    def __init__(self, video_ids: list = None, max_threads: int = None):
        self.lock = threading.Lock()
        self.screen = Overwriteable()
        self.message_queue = queue.Queue()
        self.message_thread = DHMessageThread(
            self.lock,
            self.screen,
            self.message_queue)
        if video_ids is None:
            self.videos = None
        else:
            self.videos = store_video_data(video_ids)
        self.max_threads = max_threads

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of data for the message handler
        """
        self.message_queue.put(data)

    def run(self) -> None:
        """Run the download handler operations

        Starts the message handler.  Exits early if no video IDs are provided.
        Fills task queue and prepares task threads.  Starts task threads and
        marks all for stopping on an empty queue.  Joins the task queue to wait
        until all tasks are complete.  Joins the task threads.  Stops the
        instance message handlers.
        """
        self.message_thread.start()
        if self.videos is None or len(self.videos) == 0:
            self.message({
                "idx": 0,
                "text": "\033[1;31m✘\033[m No video IDs provided",
            })
            self.stop()
            return

        time_start = time.time()

        l = len(self.videos)
        s = "" if l == 1 else "s"
        self.message({
            "idx": 0,
            "text": f"\033[1;32m⁜\033[m Downloading {l} video{s}",
        })

        task_queue = queue.Queue()
        for (idx, vid) in enumerate(self.videos):
            vid.update({
                "idx": idx + 1,  # Hardcoded offset
                "ytdlp_options": self.ytdlp_options.copy(),
            })
            task_queue.put(vid)
            self.message({
                "idx": vid.get("idx"),
                "text": vid.get("status").status,
            })

        workers = []
        if self.max_threads is None:
            n_workers = 1
        else:
            n_workers = self.max_threads
        for _ in range(0, n_workers):
            workers.append(DHTaskThread(task_queue, self.message_queue))

        for w in workers:
            w.start()
        for w in workers:
            w.stop()

        task_queue.join()
        for w in workers:
            w.join()

        time_end = time.time()

        self.message({
            "idx": 0,
            "text": "\033[1;32m⁜\033[m Downloaded {l} video{s} in {t}s".format(
                l=l,
                s=s,
                t=round(time_end - time_start, 1)),
        })

        self.stop()

    def stop(self) -> None:
        """Stop the instance message handlers"""
        self.message_queue.join()
        self.message_thread.stop()
        self.message_thread.join()


# Main function
# -----------------------------------------------------------------------------


def main():
    """Basic command-line usage"""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "video_ids",
        metavar="ID",
        type=str,
        nargs="+",
        help="Youtube video links or IDs to download")

    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=None,
        help="Number of threads to use for operations")

    args = vars(parser.parse_args())

    dh = DownloadHandler(
        args.get("video_ids"),
        max_threads=args.get("threads"))

    dh.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
