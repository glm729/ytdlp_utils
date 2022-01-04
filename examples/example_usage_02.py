#!/usr/bin/env python3.8


if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.expanduser("~/ytdlp_utils/ytdlp_utils/"))

    # MP batch handler:
    from multiprocess_runner import MultiprocessRunner
    mh = MultiprocessRunner(sys.argv[1])
    mh.run()

    # OR

    # Non-MP batch handler:
    from batch_handler import BatchHandler
    bh = BatchHandler()
    bh.read_video_links(sys.argv[1])
    bh.run()

    # OR

    # Playlist handler:
    from playlist_handler import PlaylistHandler
    ph = PlaylistHandler(sys.argv[1])
    ph.run()
