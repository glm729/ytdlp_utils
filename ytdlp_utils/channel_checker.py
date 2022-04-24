#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import argparse
import json
import queue
import sys
import threading
import time
import yt_dlp

from download_handler import DHMessageThread
from download_handler import Status
from overwriteable import Overwriteable


# Function definitions
# -----------------------------------------------------------------------------


def check_data(task, data) -> tuple:
    """Check incoming data against existing task data

    @param task Current channel data
    @param data Incoming recent uploads data
    @return 3-tuple; channel data object, list of new (i.e. changed) titles,
    and list of new videos
    """
    # Initialise stores for title changes and new videos
    new_title = []
    new_video = []
    # Loop over the incoming data
    for n_entry in data:
        # Assume it's a new video
        is_new = True
        for o_entry in task.get("recent_uploads"):
            # If same URI, mark as not new and check for title change
            if n_entry.get("uri") == o_entry.get("uri"):
                is_new = False
                n_title = n_entry.get("title")
                o_title = o_entry.get("title")
                # If the title differs, push to the changed title list
                if n_title != o_title:
                    new_title.append((o_title, n_title))
        # If still new after looping all data, push to the new video list
        if is_new:
            new_video.append(n_entry.get("title"))
    # Build an output dict in the common channel data format
    output = {
        "recent_uploads": data,
        "title": task.get("title"),
        "uri": task.get("uri"),
    }
    # Return the 3-tuple of output data, changed titles, and new videos
    return (output, new_title, new_video)


def status_new_data(status, new_title: list, new_video: list):
    """Update a status line with new data

    If there are any new data, update the given status line with some fancy
    output.  If there are no new data, mention that too.

    @param new_title List of changed titles
    @param new_video List of new videos
    @return Mutated status object; updated prefix and body
    """
    prefix = "\033[1;32m✔\033[m"
    body = status_new_data_body(new_title, new_video)
    status.update({ "prefix": prefix, "body": body, })
    return status


def status_new_data_body(new_title: list, new_video: list) -> str:
    """Get the text body for updating status line data

    Wrapped for short-circuit if no new data, and due to the complexity of
    latter operations (a bit of a jumble).

    @param new_title List of new (changed) video titles
    @param new_video List of new videos
    @return Body text (string)
    """
    # Store the lengths, and check if there's nothing to do
    l_t = len(new_title)
    l_v = len(new_video)
    if l_t == 0 and l_v == 0:
        return "\033[34mNo new data\033[m"
    # Initialise stores for text data
    t_data_header = []
    t_data_body = []
    # If at least one changed title, add data
    if l_t > 0:
        s_t = "" if l_t == 1 else "s"
        t_data_new_title = [
            f"↳ \033[33mChanged title{s_t}\033[m:",
            *map(lambda x: f"  - {x[0]} => {x[1]}", new_title),
        ]
        t_data_header.append(f"\033[33m{l_t} title{s_t} changed")
        t_data_body.extend(t_data_new_title)
    # If at least one new video, add data
    if l_v > 0:
        s_v = "" if l_v == 1 else "s"
        t_data_new_video = [
            f"↳ \033[32mNew video{s_v}\033[m:",
            *map(lambda x: f"  - {x}", new_video),
        ]
        t_data_header.append(f"\033[32m{l_v} new video{s_v}\033[m")
        t_data_body.extend(t_data_new_video)
    # Join the body header text and body additional text
    t_header = "; ".join(t_data_header)
    t_body = "\n".join(t_data_body)
    # Return the combined text for the body
    return f"{t_header}\n{t_body}"


# Class definitions
# -----------------------------------------------------------------------------


class CustomLogger:
    """Sink/Ignore all messages"""

    def __init__(self):
        pass

    def debug(self, message):
        pass

    def error(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass


class CCMessageThread(DHMessageThread):
    """Subclassing to keep the `CC` naming convention"""
    pass


class CCTaskThread(threading.Thread):

    def __init__(self, task_queue, result_queue, message_queue, ytdlp_options):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.message_queue = message_queue
        self.ytdlp_options = ytdlp_options

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of message data
        """
        self.message_queue.put(data)

    def process(self, task: dict) -> None:
        """Process a given task; request channel data and check

        Marks the status as requesting.  Requests the channel data using the
        instance yt_dlp options.  Reduces data and checks for changed titles
        and new videos.  Updates task status with respect to new data, if any.
        Returns results object, i.e. channel data returned by yt_dlp ops.

        @param task Task data to process
        @return New channel data from yt_dlp.YoutubeDL
        """
        task.get("status").update({
            "prefix": "\033[1;33m?\033[m",
            "body": "\033[36mRequesting channel data\033[m",
        })
        self.update_status(task)

        with yt_dlp.YoutubeDL(self.ytdlp_options) as yt:
            data = yt.extract_info(task.get("uri"), download=False)

        data_reduced = list(map(
            lambda x: { "title": x.get("title"), "uri": x.get("url"), },
            data.get("entries")))

        (result, new_title, new_video) = check_data(task, data_reduced)

        task.update({
            "status": status_new_data(
                task.get("status"),
                new_title,
                new_video),
        })
        self.update_status(task)

        return result

    def run(self):
        """Run the ChannelChecker task handler"""
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.task_queue.get(timeout=0.2)
                result = self.process(task)
                self.result_queue.put(result)
                self.task_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self):
        """Stop the task thread operations"""
        self._stopevent.set()

    def update_status(self, task: dict) -> None:
        """Update a task status message in the instance Overwritable

        @param task Task data dict
        """
        self.message({
            "idx": task.get("idx"),
            "text": task.get("status").status,
        })


class CCResultThread(threading.Thread):

    def __init__(self, result_queue):
        super().__init__(daemon=True)
        self._stopevent = threading.Event()
        self.result = []
        self.result_queue = result_queue

    def run(self):
        """Run operations for collecting results queue data"""
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.result_queue.get(timeout=0.2)
                self.result.append(task)
                self.result_queue.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self):
        """Stop the result thread operations"""
        self._stopevent.set()


class ChannelChecker:

    def __init__(self, data, n_videos: int = 6, n_threads: int = None):
        self.lock = threading.Lock()
        self.message_queue = queue.Queue()
        self.screen = Overwriteable()
        self.message_thread = CCMessageThread(
            self.lock,
            self.screen,
            self.message_queue)
        self.data = data
        self.n_videos = n_videos
        self.n_threads = n_threads

    def message(self, data: dict) -> None:
        """Put a message on the instance message queue

        @param data Dict of message data
        """
        self.message_queue.put(data)

    def run(self):
        """Run the ChannelChecker

        TODO: More doc
        """
        self.message_thread.start()
        l = len(self.data)
        if l == 0:
            self.message({
                "idx": 0,
                "text": "\033[1;31m✘\033[m No channel data provided",
            })
            self.stop()
            return
        s = "" if l == 1 else "s"
        self.message({
            "idx": 0,
            "text": f"\033[1;32m⁜\033[m Checking {l} channel{s}",
        })

        time_start = time.time()

        ytdlp_options = {
            "extract_flat": True,
            "logger": CustomLogger(),
            "playlistend": self.n_videos,
        }

        status_header_pw = max(map(lambda x: len(x.get("title")), self.data))

        task_queue = queue.Queue()
        result_queue = queue.Queue()
        result_thread = CCResultThread(result_queue)

        for (idx, dat) in enumerate(self.data):
            status = Status({
                "prefix": "\033[33m?\033[m",
                "header": "\033[35m{t}\033[m".format(
                    t=dat.get("title").ljust(status_header_pw)),
                "body": "\033[30mPending\033[m",
            })
            dat.update({
                "idx": idx + 1,
                "status": status,
            })
            self.message({
                "idx": idx + 1,  # Hardcoded offset
                "text": dat.get("status").status,
            })
            task_queue.put(dat)

        if self.n_threads is None:
            n_threads = len(self.data)
        else:
            n_threads = self.n_threads

        worker_threads = []
        for _ in range(0, n_threads):
            worker_threads.append(
                CCTaskThread(
                    task_queue,
                    result_queue,
                    self.message_queue,
                    ytdlp_options))

        result_thread.start()

        for worker in worker_threads:
            worker.start()
        for worker in worker_threads:
            worker.stop()

        task_queue.join()
        for worker in worker_threads:
            worker.join()

        result_thread.stop()
        result_thread.join()

        result = list(sorted(
            result_thread.result,
            key=lambda x: x.get("title").lower()))

        time_end = time.time()

        self.message({
            "idx": 0,
            "text": "\033[1;32m⁜\033[m {l} channel{s} checked in {t}s".format(
                l=l,
                s=s,
                t=str(round(time_end - time_start, 1))),
        })

        self.stop()

        return result

    def stop(self) -> None:
        """Stop the instance message handlers"""
        self.message_queue.join()
        self.message_thread.stop()
        self.message_thread.join()


# Main function
# -----------------------------------------------------------------------------


def main():
    """
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file_path",
        help="File path for the channel data JSON",
        type=str)
    parser.add_argument(
        "-n",
        "--number",
        help="Number of videos for which to check",
        type=int,
        default=6)
    parser.add_argument(
        "-t",
        "--threads",
        help="Number of threads to use for requesting channel data",
        type=int,
        default=None)

    args = parser.parse_args()

    with open(args.file_path, "r") as fh:
        data = json.loads(fh.read())

    cc = ChannelChecker(
        data=data,
        n_videos=args.number,
        n_threads=args.threads)

    result = cc.run()

    with open(args.file_path, "w") as fh:
        fh.write(json.dumps(result, indent=4) + "\n")


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
