#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import queue
import sys
import time
import yt_dlp

from download_handler import Status
from download_handler import Video

from download_handler import DHTaskThread
from download_handler import DownloadHandler


# Function definitions
# -----------------------------------------------------------------------------


def get_playlist_data(data: dict, ytdlp_options: dict) -> dict:
    """Create the required set of video data from the playlist info

    @param data
    @param ytdlp_options
    """
    playlist_title = data.get("title")
    entries = data.get("entries")
    l = len(entries)
    lsl = len(str(l))
    video_data = store_video_data(
        list(map(
            lambda x: x.get("id"),
            entries)))
    for (i, d) in enumerate(video_data):
        d.update(**get_video_data(i, entries[i]))
        opt = ytdlp_options.copy()
        opt.update({
            "outtmpl": "%(uploader)s/{p}/{i}__%(title)s.%(ext)s".format(
                p=playlist_title,
                i=str(i + 1).rjust(lsl, "0")),
        })
        d.update({ "ytdlp_options": opt, })
    return video_data


def get_video_data(idx: int, data: dict) -> list:
    """Subset the required video data from the playlist data entry

    @param idx Index of the current video
    @param data Dict of video data
    """
    return {
        "id": data.get("id"),
        "idx": idx + 1,  # Hardcoded offset
        "title": data.get("title"),
    }


def store_video_data(video_ids) -> list:
    """Prepare a default set of data for each video ID

    @param video_ids List or tuple of video IDs to store
    @return List of dicts; Video and StatusLine per video ID provided
    """
    l = len(video_ids)
    pw = len(str(l))
    prefix = "\033[33m?\033[m"
    body = "\033[30mPending\033[m"
    output = []
    for (idx, vid) in enumerate(video_ids):
        header = "\033[35mVideo {c} / {t}\033[m".format(
            c=str(idx + 1).rjust(pw, " "),
            t=l)
        output.append({
            "status": Status(prefix, header, body),
            "video": Video(vid),
        })
    return output


# Auxiliary class definitions
# -----------------------------------------------------------------------------


class SinkLogger:
    """Custom logger definition for requesting playlist data

    Skips all messages.
    """

    def __init__(self):
        pass

    def debug(self, m: str) -> None:
        pass

    def error(self, m: str) -> None:
        pass

    def info(self, m: str) -> None:
        pass

    def warning(self, m: str) -> None:
        pass


# PlaylistHandler class definitions
# -----------------------------------------------------------------------------


class PlaylistHandler(DownloadHandler):
    """Handle batch-downloading of Youtube playlists, using yt-dlp"""

    ytdlp_options_playlist = {
        "extract_flat": True,
    }

    def __init__(self, playlist_id: str, max_threads: int = 4):
        super().__init__(max_threads=max_threads)
        self.id = playlist_id

    def run(self) -> None:
        """Run the playlist handler operations

        Starts the message handler.  Exits early if no video IDs are provided.
        Fills task queue and prepares task threads.  Starts task threads and
        marks all for stopping on an empty queue.  Joins the task queue to wait
        until all tasks are complete.  Joins the task threads.  Stops the
        instance message handlers.
        """
        self.message_thread.start()
        time_start = time.time()

        self.message({
            "idx": 0,
            "text": "\033[1;33m?\033[m Requesting playlist data",
        })

        ytdlp_options_playlist = self.ytdlp_options_playlist.copy()
        ytdlp_options_playlist.update({ "logger": SinkLogger(), })

        with yt_dlp.YoutubeDL(ytdlp_options_playlist) as yt:
            self.videos = get_playlist_data(
                yt.extract_info(self.id),
                self.ytdlp_options.copy())

        l = len(self.videos)
        s = "" if l == 1 else "s"
        self.message({
            "idx": 0,
            "text": f"\033[1;32m⁜\033[m Downloading {l} video{s}",
        })

        task_queue = queue.Queue()
        for (idx, vid) in enumerate(self.videos):
            task_queue.put(vid)
            self.message({
                "idx": vid.get("idx"),
                "text": vid.get("status").status,
            })

        workers = []
        if self.max_threads is None:
            n_workers = len(self.videos)
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


# Main function
# -----------------------------------------------------------------------------


def main(playlist_id: str) -> None:
    """Example / Testing operations"""
    ph = PlaylistHandler(playlist_id)
    ph.run()


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise RuntimeError("Incorrect number of arguments")
    main(sys.argv[1])
