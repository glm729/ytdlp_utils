#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import json
import queue
import threading
import time
import yt_dlp

from message_handler import MessageHandler


# Custom logger definition
# -----------------------------------------------------------------------------


class ChannelCheckerLogger:

    def __init__(self, handler):
        self._handler = handler

    def debug(self, message):
        pass

    def error(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass


# Class definition
# -----------------------------------------------------------------------------


class ChannelChecker:


    _ytdlp_defaults = {
        "extract_flat": True
    }


    def __init__(self, file_path: str, n_videos: int = 6, n_threads: int = 1):
        self.file_path = file_path
        self.n_threads = n_threads
        self.n_videos = n_videos


    # ---- Public methods


    def run(self) -> None:
        """Public run method

        Initialises and starts message handler.  Ends early if reading and
        parsing the channel data fails.  Instantiates the logger and prepares
        yt_dlp options.  Requests all channel data and processes.  Notifies of
        completion and timing, and ends message handler.
        """

        # Start the message handler, but kick if failed to read file
        self._init_message_handler()
        if not self._read_file(self.file_path):
            self._end_message_handler()
            return

        # Initialise required run data
        time_start = time.time()
        self._logger = ChannelCheckerLogger(self)
        ytdlp_options = self._ytdlp_defaults.copy()
        ytdlp_options.update({
            "logger": self._logger,
            "playlistend": self.n_videos,
        })

        # Initialise threading and queue requirements
        task_queue = queue.Queue()
        result_queue = queue.Queue()
        for data in self.channel_data:
            task_queue.put(data)

        # Initialise task threads
        task_threads = []
        for _ in range(0, self.n_threads):
            task_threads.append(threading.Thread(
                target=self._fun_thread_task,
                args=(task_queue, result_queue, ytdlp_options),
                daemon=True))

        # Initialise results gathering requirements and start results thread
        self._loop = True
        self._lock = threading.RLock()
        self.result = []
        result_thread = threading.Thread(
            target=self._fun_thread_result,
            args=(result_queue,),
            daemon=True)
        result_thread.start()

        # Start all task threads and schedule join
        for t in task_threads:
            t.start()
        for t in task_threads:
            t.join()

        # Join the task and results queues, and end the results thread loop
        task_queue.join()
        result_queue.join()
        self._loop = False
        result_thread.join()

        # Sort the results data by uploader title, and write back to the file
        new_data = list(sorted(
            self.result,
            key=lambda x: x.get("title").lower()))
        self._write_file(self.file_path, new_data)

        # Notify completion
        text = "All channels checked in {t:.1f}s"
        self._message(text.format(t=time.time() - time_start), "ok")

        # Clean up the message handler
        self._end_message_handler()


    # ---- Private methods


    def _append_result(self, result) -> None:
        """Append a result to the instance results list

        Wrap appending results data in the instance recursive lock, to avoid
        collisions.  There's only one results thread, but it's not the main
        thread, so its access should be locked.

        @param result Results data to append
        """
        self._lock.acquire()
        try:
            self.result.append(result)
        finally:
            self._lock.release()


    def _check_channel(self, data, yt) -> dict:
        """Extract and check incoming data for the given channel

        @param data Data for the current channel to check.
        @param yt yt_dlp.YoutubeDL instance to use for extracting info.
        """
        self._message(f"{data.get('title')}: Checking recent uploads", "info")
        new_titles = []
        new_videos = []
        new_data = list(map(
            lambda x: { "title": x.get("title"), "uri": x.get("url"), },
            yt.extract_info(data.get("uri"), download=False).get("entries")))
        for new in new_data:
            new_video = True
            for old in data.get("recent_uploads"):
                if new.get("uri") == old.get("uri"):
                    new_video = False
                    if (nt := new.get("title")) != (ot := old.get("title")):
                        new_titles.append((ot, nt))
            if new_video:
                new_videos.append(new.get("title"))
        output = {
            "recent_uploads": new_data,
            "title": data.get("title"),
            "uri": data.get("uri"),
        }
        self._check_new_titles(output, new_titles)
        self._check_new_videos(output, new_videos)
        return output


    def _check_new_titles(self, new_data, new_titles) -> None:
        """Check for and notify of title changes for the given channel

        @param new_data New data for the channel to check.
        @param new_titles List of changed-title 2-tuples for which to notify.
        """
        l = len(new_titles)
        if l == 0:
            return
        s = '' if l == 1 else "s"
        title_changes = map(lambda x: f"\n{' ' * 9}--> ".join(x), new_titles)
        text = f"{new_data.get('title')}: {l} video title{s} changed:"
        self._message(f"\n{' ' * 7}- ".join((text, *title_changes)), "warn")


    def _check_new_videos(self, new_data, new_videos) -> None:
        """Check for an notify of new videos for the given channel

        @param new_data New data for the channel to check.
        @param new_videos List of new video titles for which to notify.
        """
        l = len(new_videos)
        t = new_data.get("title")
        if l == 0:
            self._message(f"{t}: No new uploads found", "info")
            return
        s = '' if l == 1 else "s"
        text = f"\n{' ' * 7}- ".join((f"{t}: {l} new upload{s}:", *new_videos))
        self._message(text, "ok")


    def _end_message_handler(self) -> None:
        """End the instance message handler"""
        self._message_handler.end()


    def _fun_thread_result(self, result_queue) -> None:
        """Result thread function

        Set a timeout on the `get` call to reduce processor load.  Wrap
        appending the results data in a recursive lock to avoid collisions.

        @param result_queue Queue from which to get results data
        """
        while self._loop:
            try:
                result = result_queue.get(timeout=0.2)
                self._append_result(result)
                result_queue.task_done()
            except queue.Empty:
                pass


    def _fun_thread_task(
            self,
            task_queue,
            result_queue,
            ytdlp_options) -> None:
        """Task thread function

        Given a task queue to get from, a results queue to put into, and an
        options object to use for yt_dlp, check video data for each channel
        dataset grabbed from the task queue.  End when the task queue is empty.

        @param task_queue Queue from which to get tasks
        @param result_queue Queue for which to put completed task results
        @param ytdlp_options Dict of options to use for the `yt_dlp.YoutubeDL`
        object
        """
        with yt_dlp.YoutubeDL(ytdlp_options) as yt:
            while True:
                try:
                    task = task_queue.get(block=False)
                    result = self._check_channel(task, yt)
                    self._put_result(result_queue, result)
                    task_queue.task_done()
                except queue.Empty:
                    break


    def _init_message_handler(self) -> None:
        """Initialise and start the instance message handler"""
        self._message_handler = MessageHandler()
        self._message_handler.start()


    def _message(self, text: str, form: str) -> None:
        """Print a message via the instance message handler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)


    def _put_result(self, result_queue, result) -> None:
        """Put a result in the results queue

        Lock putting the result to avoid collisions.

        @param result_queue Queue in which to put results data
        @param result Results data to put in the results queue
        """
        self._lock.acquire()
        try:
            result_queue.put(result)
        finally:
            self._lock.release()


    def _read_file(self, path: str) -> bool:
        """Read, parse, and store the contents of the given channel data JSON

        @param path Path to the channel data JSON.
        """
        self._message(f"Reading channel data file: {path}", "data")
        try:
            with open(path, "r") as fh:
                data = fh.read()
        except FileNotFoundError:
            self._message(f"File does not exist: {path}", "error")
            return False
        try:
            data_json = json.loads(data)
        except json.JSONDecodeError:
            self._message(
                f"Failed to parse file as JSON: {path}",
                "error")
            return False
        self.channel_data = data_json
        return True


    def _write_file(self, path: str, data) -> None:
        """Write the updated channel data JSON to the given file path

        Might need a try-except block or two.

        @param path File path for which to write channel data.
        @param data Channel data to write to the given path.
        """
        self._message(f"Writing channel data to file: {path}", "data")
        data = json.dumps(data, indent=2)
        with open(path, "w") as fh:
            fh.write(f"{data}\n")


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":

    import argparse

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

    cc = ChannelChecker(
        file_path=args.file_path,
        n_videos=args.number,
        n_threads=args.threads)

    cc.run()
