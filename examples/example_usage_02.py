#!/usr/bin/env python3.8


if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.expanduser("~/ytdlp_utils/ytdlp_utils/"))

    # MP batch handler:
    from multiprocess_runner import MultiprocessRunner
    MultiprocessRunner(sys.argv[1]).run()

    # OR

    # Non-MP batch handler:
    from batch_handler import BatchHandler
    bh = BatchHandler()
    bh.read_video_links(sys.argv[1])
    bh.run()
