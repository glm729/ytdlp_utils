#!/usr/bin/env python3.8


# Class definition
# -----------------------------------------------------------------------------


class Playlist:

    def __init__(self, playlist_id: str, index: int = 1, length: int = 1):
        self.id = playlist_id
        self.length = length
        self.length_str = str(length)
        self.set_index(index)

    # ---- Public methods

    def set_index(self, index):
        """Set the current index for the playlist instance

        @param index Index to set as current.
        """
        self.index = index
        self.index_str = str(index)
        self.index_padded = self.index_str.rjust(len(self.length_str), " ")

    def request_data(self, yt) -> dict:
        """Request the data for the playlist

        Uses a `yt_dlp.YoutubeDL` object.  Remember to use `extract_flat`!

        @param yt yt_dlp.YoutubeDL object to use for requesting data
        extraction.
        """
        l = 0
        videos = []
        data = yt.extract_info(self.id)
        title = data.get("title")
        for (idx, video) in enumerate(data.get("entries")):
            l += 1
            videos.append({
                "id": video.get("id"),
                "index": idx + 1,
                "title": video.get("title"),
                "uri": video.get("url"),
            })
        # Add a useful `outtmpl` for each individual video
        for video in videos:
            video.update({
                "outtmpl": "%(uploader)s/{pt}/{i}__%(title)s.%(ext)s".format(
                    pt=title,
                    i=str(video.get("index")).rjust(len(str(l)), "0"),
                    vt=video.get("title")),
            })
        self.entries = videos
        self.length = l
        self.length_str = str(l)
        self.title = title
        self.data = dict(map(
            lambda x: (x, getattr(self, x)),
            ("entries", "id", "length", "length_str", "title")))
        return self.data
