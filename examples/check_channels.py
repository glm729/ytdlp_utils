#!/usr/bin/env python3.8


# Example usage for checking the channels detailed in the provided JSON file.
# This is the script I use for checking the data stored on an external drive,
# and be aware that it uses a hardcoded path to the module.


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import os
    import sys

    sys.path.append(os.path.expanduser("~/ytdlp_utils/ytdlp_utils/"))
    from channel_checker import ChannelChecker

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
