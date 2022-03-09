#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import argparse
import io
import json
import queue
import sys
import threading
import time
import yt_dlp

from overwriteable import Overwriteable
from status_line import ChannelStatus


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




class CCTaskThread(threading.Thread):

    _stopevent = threading.Event()

    def __init__(self, parent, task_queue, result_queue, ytdlp_options):
        super().__init__()
        self.daemon = True
        self.p = parent
        self.qt = task_queue
        self.qr = result_queue
        self.opt = ytdlp_options


    def check_data(self, task, data):
        """Check the incoming data against the existing data

        @param task Current channel data
        @param data Incoming recent uploads data
        """
        new_title = []
        new_video = []
        for new in data:
            is_new = True
            for old in task.get("recent_uploads"):
                if new.get("uri") == old.get("uri"):
                    is_new = False
                    if (nt := new.get("title")) != (ot := old.get("title")):
                        new_title.append((ot, nt))
            if is_new:
                new_video.append(new.get("title"))
        output = {
            "recent_uploads": data,
            "title": task.get("title"),
            "uri": task.get("uri"),
        }
        return (output, new_title, new_video)


    def request_data(self, task):
        """Request recent videos data for a given channel

        @param task Dict of channel data
        @return List of dicts; list of top n_videos recent video uploads, with
        only the title and URI
        """
        with yt_dlp.YoutubeDL(self.opt) as yt:
            data = yt.extract_info(task.get("uri"), download=False)
        return list(map(
            lambda x: { "title": x.get("title"), "uri": x.get("url"), },
            data.get("entries")))


    def run(self) -> None:
        """Run thread operations

        Get tasks from a task queue, and process the data.  Stop when no more
        tasks are available from the queue and the stop marker is set.
        """
        # Clear the stop event if already set
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                (status, task) = self.qt.get(timeout=0.2)
                self.mark_requesting(status)
                data = self.request_data(task)
                (result, new_title, new_video) = self.check_data(task, data)
                self.qr.put(result)
                self.qt.task_done()
                self.mark_complete(status, result, new_title, new_video)
            except queue.Empty:
                if self._stopevent.is_set():
                    break


    def mark_complete(self, status, result, new_title, new_video) -> None:
        """Mark the current status line as complete

        Provide info on changed and new titles, if any.

        @param status
        @param result
        @param new_title
        @param new_video
        """
        prefix = "\033[1;32m✔\033[m"
        suffix = "\033[32mData retrieved\033[m"
        suffix_data = []
        nt = False
        nv = False
        if (l := len(new_title)) > 0:
            s = '' if l == 1 else "s"
            suffix_data.append(f"\033[33m{l} title{s} changed\033[m")
            nt = "\n  ↳ \033[33mChanged title{s}\033[m:\n{t}".format(
                s=s,
                t="\n".join(map(
                    lambda x: f"    - {x[0]} => {x[1]}",
                    new_title)))
        if (l := len(new_video)) > 0:
            s = '' if l == 1 else "s"
            suffix_data.append(f"\033[32m{l} new video{s}\033[m")
            nv = "\n  ↳ \033[32mNew video{s}\033[m:\n{t}".format(
                s=s,
                t="\n".join(map(lambda x: f"    - {x}", new_video)))
        if len(suffix_data) == 0:
            suffix = "\033[34mNo new videos\033[m"
        else:
            suffix = "; ".join(suffix_data)
        if isinstance(nt, str):
            suffix += nt
        if isinstance(nv, str):
            suffix += nv
        status.set_prefix(prefix)
        status.set_suffix(suffix)
        with self.p.lock:
            self.p.screen.replace_line(status.idx, status.text)
            self.p.screen.flush()


    def mark_requesting(self, status) -> None:
        """Mark the current status line as being requested"""
        prefix = "\033[1;33m?\033[m"
        suffix = "\033[36mRequesting data\033[m"
        status.set_prefix(prefix)
        status.set_suffix(suffix)
        with self.p.lock:
            self.p.screen.replace_line(status.idx, status.text)
            self.p.screen.flush()


    def stop(self) -> None:
        """Stop the thread operations"""
        self._stopevent.set()




class CCResultThread(threading.Thread):

    _stopevent = threading.Event()

    result = []

    def __init__(self, result_queue):
        super().__init__()
        self.daemon = True
        self.qr = result_queue


    def run(self) -> None:
        """Run operations for collecting results queue data"""
        if self._stopevent.is_set():
            self._stopevent.clear()
        while True:
            try:
                task = self.qr.get(timeout=0.2)
                self.result.append(task)
                self.qr.task_done()
            except queue.Empty:
                if self._stopevent.is_set():
                    break

    def stop(self) -> None:
        """Stop thread operations"""
        self._stopevent.set()




class ChannelChecker:

    lock = threading.RLock()
    screen = Overwriteable()
    statuses = []

    def __init__(self, data, n_videos: int = 6, n_threads: int = 1):
        self.data = data
        self.n_videos = n_videos
        self.n_threads = n_threads


    def add_line(self, text: str, idx: int = None) -> None:
        """Add a line to the instance overwriteable stream

        @param text Text to add to the content
        @param idx Optional index at which to add the line; defaults to
        appending the line
        """
        self.screen.add_line(text, idx)
        self.screen.flush()


    def replace_line(self, idx: int, text: str) -> None:
        """Replace a line in the overwriteable stream

        @param idx Index at which to replace the line
        @param text Text with which to replace the line
        """
        self.screen.replace_line(idx, text)
        self.screen.flush()


    def run(self) -> None:
        """Check all channels provided in the input data"""
        self.add_line("Starting operations...")
        l = len(self.data)
        s = '' if l == 1 else "s"
        if l == 0:
            self.replace_line(0, "\033[1;31m✘\033m  No channel data provided!")
            return
        self.replace_line(0, f"\033[1;32m⁜\033[m Checking {l} channel{s}")

        # Set yt-dlp options dict
        ytdlp_options = {
            "extract_flat": True,
            "logger": CustomLogger(),
            "playlistend": self.n_videos,
        }

        # Initialise task and result queues
        qt = queue.Queue()
        qr = queue.Queue()

        # Prepare data for visuals
        c0pw = max(map(lambda x: len(x.get("title")), self.data))
        pending_p = "\033[33m?\033[m"
        pending_t = "\033[30mPending\033[m"
        l = len(self.screen.content)

        # Put tasks in the queue
        for (i, d) in enumerate(self.data):
            status = ChannelStatus(
                    i + 1,
                    d.get("title"),
                    pending_p,
                    pending_t,
                    c0pw)
            self.statuses.append(status)
            qt.put((status, d))
            self.screen.add_line(status.text)
        self.screen.flush()

        # Generate task threads
        task_threads = list(map(
            lambda x: CCTaskThread(
                self,
                qt,
                qr,
                ytdlp_options),
            range(self.n_threads)))

        # Generate results collector thread
        result_thread = CCResultThread(qr)

        # Start the task threads
        for t in task_threads:
            t.start()

        # Start the result thread
        result_thread.start()

        # Mark the task threads to stop, and wait for them to join
        for t in task_threads:
            t.stop()
        for t in task_threads:
            t.join()

        # Mark the result thread to stop, and wait for it to join
        result_thread.stop()
        result_thread.join()

        # Retrieve the results
        result = result_thread.result

        # Return the output data
        return result




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
        default=1)

    args = parser.parse_args()

    with open(args.file_path, "r") as fh:
        data = json.loads(fh.read())

    cc = ChannelChecker(
        data=data,
        n_videos=args.number,
        n_threads=args.threads)

    result = cc.run()

    # with open(args.file_path, "w") as fh:
    #     fh.write(json.dumps(result, indent=4) + "\n")


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
