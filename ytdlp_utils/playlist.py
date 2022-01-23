#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import subprocess


# Class definition
# -----------------------------------------------------------------------------


class Playlist:

    def __init__(self, playlist_id, index=1, length=1):
        self.id = playlist_id
        self.length = length
        self.length_str = str(length)
        self.set_index(index)

    # ---- Public methods

    def get_playlist_data(self):
        """Request the data for the playlist

        Primarily for the purpose of discovering and storing playlist length.
        """
        cmd = ("yt-dlp", "--flat-playlist", "--print", "id", self.id)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if proc.wait() == 0:
            count = 0
            while (l := proc.stdout.readline()):
                count += 1
            self.length = count
            self.length_str = str(count)
            self.set_index(self.index)
        # TODO: Subprocess failure is currently unhandled!
        # This gap may be adequately handled by the defaults.

    def set_index(self, index):
        """Set the current index for the playlist instance

        @param index Index to set as current.
        """
        self.index = index
        self.index_str = str(index)
        self.index_padded = self.index_str.rjust(len(self.length_str), " ")
