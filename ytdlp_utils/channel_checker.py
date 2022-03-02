#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import io
import queue
import random
import sys
import threading
import time
# import yt_dlp


# Class definitions
# -----------------------------------------------------------------------------




class Overwriteable:

    buffer = io.StringIO(initial_value='', newline="\n")
    content = []
    lastlines = 0

    def __init__(self, stream=sys.stdout):
        self.stream = stream


    def _build(self) -> None:
        """Build the buffer content, using the content store"""
        # Clear out the buffer
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)

        # Get the content as a string and print into the buffer
        string = "\n".join(self.content)
        print(string, end="\n", file=self.buffer)


    def add_line(self, text: str, idx: int = None) -> None:
        """Add a line to the content store

        @param text
        @param idx
        """
        if idx is None:
            self.content.append(text)
            return
        self.content.insert(idx, text)


    def flush(self) -> None:
        """Flush the string buffer contents to the instance stream

        Instance stream defaults to `sys.stdout`.
        """
        # Build the buffer content
        self._build()

        # If more than one line, move to top and clear the text below
        if self.lastlines > 0:
            print(f"\033[{self.lastlines}F\033[J", end='', file=self.stream)

        # Seek the start of the string buffer and read
        self.buffer.seek(0, 0)
        string = self.buffer.read()

        # Print string buffer contents to the stream and count newlines
        print(string, end='', file=self.stream)
        self.lastlines = string.count("\n")

        # Seek the start of the string buffer and truncate (clear data)
        self.buffer.seek(0, 0)
        self.buffer.truncate(0)


    def redraw(self) -> None:
        """

        Might rename `flush` to `redraw`.

        """
        pass


    def redraw_at(self, x: int, y: int) -> None:
        """Redraw a specific character at a given set of coordinates

        @param x
        @param y
        """
        move_x = x  # ... TODO: Check how 0 is handled
        move_y = self.lastlines - y


    def redraw_line(self, idx: int) -> None:
        """Redraw a specified line of content

        Will this even work?  Needs testing!

        @param idx Index of the content line to redraw
        """
        move = self.lastlines - idx
        print(f"\033[{move}F\033[2K", end='', file=self.stream)
        print(self.content[idx], end='', file=self.stream)
        # ... TODO
        # Reset position to end of content


    def replace_line(self, idx: int, text: str) -> None:
        """Replace a content line

        @param idx Index of the string to replace
        @param text Text to insert
        """
        self.content.pop(idx)
        self.content.insert(idx, text)


    # def print(self, text, end: str = "\n") -> None:
    #     """Print text to the overwriteable buffer
    #     @param text Text to print into the buffer
    #     @param end Ending character; defaults to newline
    #     """
    #     self.buffer.seek(0, 2)  # seek 0 bytes from position 2 == seek end
    #     print(text, end=end, file=self.buffer)




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

    def __init__(self, lock, screen, task_queue, result_queue, ytdlp_options):
        super().__init__()
        self.daemon = True
        self.lock = lock
        self.screen = screen
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
                    if (nt := new.get("title")) == (ot := old.get("title")):
                        new_title.append((ot, nt))
            if is_new:
                new_video.append(new.get("title"))
        output = {
            "recent_uploads": data,
            "title": task.get("title"),
            "uri": task.get("uri"),
            "new_title": new_title,
            "new_video": new_video,
        }
        return output


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
                (idx, task) = self.qt.get(timeout=0.2)
                with self.lock:
                    self.screen.replace_line(idx, "Requesting data")
                    self.screen.flush()
                # data = self.request_data(task)
                # result = self.check_data(task, data)
                # self.qr.put(result)
                time.sleep(random.random() * 10)
                self.qt.task_done()
                with self.lock:
                    self.screen.replace_line(idx, "Done!")
                    self.screen.flush()
            except queue.Empty:
                if self._stopevent.is_set():
                    break


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
        """
        """
        self._stopevent.set()



class ChannelChecker:

    lock = threading.RLock()
    screen = Overwriteable()

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
            self.replace_line(0, "No channel data provided!")
            return

        # Set yt-dlp options dict
        ytdlp_options = {
            "extract_flat": True,
            "logger": CustomLogger(),
            "playlistend": self.n_videos,
        }

        # Initialise task and result queues
        qt = queue.Queue()
        qr = queue.Queue()

        # Put tasks in the queue
        l = len(self.screen.content)
        for (i, d) in enumerate(self.data):
            qt.put((l + i, d))
            self.screen.add_line("Pending")
        self.screen.flush()

        # Generate task threads
        task_threads = list(map(
            lambda x: CCTaskThread(
                self.lock,
                self.screen,
                qt,
                qr,
                ytdlp_options),
            self.data))

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


# Main function
# -----------------------------------------------------------------------------


def main():
    cc = ChannelChecker(["thingo", "whatsit"])
    cc.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
