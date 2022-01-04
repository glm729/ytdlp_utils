#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import json
import queue
import subprocess
import threading

from message import Message


# Class definitions
# -----------------------------------------------------------------------------


class MessageHandler:

    def __init__(self):
        pass

    # ---- Public methods

    def end(self) -> None:
        """End message handler operations"""
        self._queue.join()
        self._loop = False
        self._thread.join()

    def message(self, text: str, form: str) -> None:
        """Enqueue a message to print

        @param text Message text.
        @param form Message form.
        """
        self._enqueue_message(Message(text=text, form=form))

    def start(self) -> None:
        """Start message handler operations"""
        self._loop = True
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._fun_thread, daemon=True)
        self._thread.start()

    # ---- Private methods

    def _enqueue_message(self, message: Message) -> None:
        """Wrap enqueuing a message in a recursive lock

        @param message Message object to enqueue.
        """
        self._lock.acquire()
        try:
            self._queue.put(message)
        finally:
            self._lock.release()

    def _fun_thread(self) -> None:
        """Message thread target function"""
        while self._loop:
            try:
                self._print(self._queue.get(timeout=0.2))
                self._queue.task_done()
            except queue.Empty:
                pass

    def _print(self, message: Message) -> None:
        """Wrap message printing in a recursive lock

        @param message Message object to print.
        """
        self._lock.acquire()
        try:
            message.print()
        finally:
            self._lock.release()


class ChannelChecker:

    def __init__(self, file_path: str, n: int = 6):
        self._n = n
        self._n_str = str(n)
        self._path = file_path

    # ---- Public methods

    def run(self):
        """Main run method

        Starts and ends message handler.  Generates prefixes for printing.
        Checks over all results from running subprocesses.  Writes resulting
        channel data JSON, overwriting the input file.
        """
        self._init_message_handler()
        if not self._read_channel_data(self._path):
            self._close_message_handler()
            return
        self._generate_prefixes()
        result = []
        for data in self.channel_data:
            res = self._process(data)
            self._check_result(res)
            result.append(res)
        self._write_channel_data(self._export(result))
        self._message("All channel data checked", "ok")
        self._close_message_handler()

    # ---- Private methods

    def _check_result(self, result: dict) -> None:
        """Check a result for changes and provide messages

        Checks if any videos have been renamed, and checks for new videos.

        @param result Processed data from subprocess call.
        """
        # Shorthand
        recent_uploads = result.get("recent_uploads")
        p = self._prefix.get(result.get("title"))
        # Check which video IDs feature new titles
        new_title = []
        for recent in recent_uploads:
            if recent.get("_title", None) is not None:
                new_title.append(recent)
        # Check which are new videos
        new_video = tuple(filter(lambda x: x.get("is_new"), recent_uploads))
        # Print a message for changed titles
        if (l := len(new_title)) > 0:
            changed = tuple(map(
                lambda x: f"{x.get('_title')} => {x.get('title')}",
                new_title))
            s = '' if l == 1 else "s"
            t = f"\n{' ' * 7}- ".join((
                f"{p}: Title changed for {l} video{s}:",
                *changed))
            self._message(t, "warn")
        # Print a message for new videos
        if (l := len(new_video)) > 0:
            titles = tuple(map(lambda x: x.get("title"), new_video))
            s = '' if l == 1 else "s"
            t = f"\n{' ' * 7}- ".join((
                f"{p}: {l} new upload{s} found:",
                *titles))
            self._message(t, "ok")
            return
        # If it gets here, there are no new uploads
        self._message(f"{p}: No new uploads", "info")

    def _close_message_handler(self):
        """End the message handler for the instance run"""
        self._message_handler.end()

    def _export(self, result: list) -> None:
        """Reduce results data for export to JSON

        @param result Final results data prior to reduction.
        """
        export = []
        for res in result:
            recent_uploads = res.get("recent_uploads")
            recent_new = []
            for recent in recent_uploads:
                recent_new.append({
                    "title": recent.get("title"),
                    "uri": recent.get("uri")
                })
            export.append({
                "recent_uploads": recent_new,
                "title": res.get("title"),
                "uri": res.get("uri")
            })
        return export

    def _generate_command(self, uri: str) -> tuple:
        """Generate the command for the given channel data

        @param uri URI for which to generate the yt-dlp command.
        """
        return (
            "yt-dlp",
            "--print",
            "%(id)s__%(title)s",
            "--flat-playlist",
            "--playlist-end",
            self._n_str,
            uri)

    def _generate_prefixes(self):
        """Generate a set of coloured prefixes for printing"""
        template = "\033[1;{c}m{t}\033[0m"
        colour_index = 30
        self._prefix = {}
        for data in self.channel_data:
            title = data.get("title")
            self._prefix.update({
                title: template.format(c=colour_index, t=title)
            })
            if colour_index >= 37:
                colour_index = 30
                continue
            colour_index += 1

    def _init_message_handler(self):
        """Initialise the message handler for the instance run"""
        self._message_handler = MessageHandler()
        self._message_handler.start()

    def _message(self, text, form):
        """Print a message via the message handler

        @param text Message text.
        @param form Message form.
        """
        self._message_handler.message(text=text, form=form)

    def _process(self, data: dict) -> dict:
        """Run a subprocess and process the output

        Checks if the data already exist, or if the title for an existing video
        has been changed.

        @param data Channel data dict to check.
        @return Processed list of data from the subprocess call.
        """
        t = f"{self._prefix.get(data.get('title'))}: Checking recent uploads"
        self._message(t, "info")
        video_data = self._subprocess(data)
        output = []
        for v in video_data:
            new_video = True
            for recent in data.get("recent_uploads"):
                # Mark as not new if the URI is already present
                if v.get("uri") == recent.get("uri"):
                    new_video = False
                    # Store the previous title if the new one differs
                    if v.get("title") != (t := recent.get("title")):
                        v.update({ "_title": t })
            v.update({ "is_new": new_video })
            output.append(v)
        # Return a dict in a format similar to the `channel_data` file
        return {
            "recent_uploads": output,
            "title": data.get("title"),
            "uri": data.get("uri")
        }

    def _subprocess(self, data: dict) -> list:
        """Run a subprocess to check recent uploads

        @param data Channel data dict for which to run the subprocess.
        @return List of data returned by the subprocess, after basic
        processing.
        """
        proc = subprocess.Popen(
            self._generate_command(data.get("uri")),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        # If the subprocess fails, return None
        if proc.wait() != 0:
            return None
        # Loop stdout lines and arrange in a certain format
        video_data = []
        while (l := proc.stdout.readline()):
            line = l.decode("utf-8").strip()
            (video_id, video_title) = line.split("__")
            video_link = f"https://www.youtube.com/watch?v={video_id}"
            video_data.append({
                "title": video_title,
                "uri": video_link
            })
        return video_data

    def _read_channel_data(self, file_path: str) -> bool:
        """Attempt to read and parse the channel data JSON

        @param file_path Path to the channel data JSON.
        """
        t = f"Reading and parsing channel data file: {file_path}"
        self._message(t, "ok")
        # Try to open the file
        try:
            with open(file_path, "r") as fh:
                data = fh.read()
        except FileNotFoundError:
            self._message(f"File does not exist: {file_path}", "error")
            return False
        # Try to parse the file data as JSON
        try:
            data_json = json.loads(data)
        except json.JSONDecodeError:
            t = f"Failed to parse file as JSON: {file_path}"
            self._message(t, "error")
            return False
        # Store in the instance and confirm success
        self.channel_data = data_json
        return True

    def _write_channel_data(self, export: list):
        """Overwrite the existing channel data JSON

        @param data Data export to convert to JSON and write to file.
        """
        self._message(f"Writing channel data to file: {self._path}", "data")
        data = json.dumps(export, indent=4)
        with open(self._path, "w") as fh:
            fh.write(data)


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    cc = ChannelChecker(sys.argv[1])
    cc.run()
