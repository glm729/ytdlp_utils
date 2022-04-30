#!/usr/bin/env python3.10


# Module imports
# -----------------------------------------------------------------------------


import argparse
import functools
import re


# Constants
# -----------------------------------------------------------------------------


REX_DEFAULT = [
    re.compile(r"[\?&]v\=(?P<id>[^\?&]+)"),                # Normal
    re.compile(r"youtube\.com\/shorts\/(?P<id>[^\?&]+)"),  # "Shorts"
    re.compile(r"youtu\.be\/(?P<id>[\?&]+)"),              # Compact
]


# Function definitions
# -----------------------------------------------------------------------------


def extract_from(data: list, rex: list) -> list:
    """Extract Youtube video IDs from a given dataset and regex dict

    @param data List of text in which to search for Youtube IDs
    @param rex List or tuple of regular expressions to use for searches
    @return List of Youtube video IDs found in the data
    """
    func = functools.partial(reduce_result, rex=rex)
    return functools.reduce(func, data, [])


def extract_from_file(path: str, rex: list) -> list:
    """Extract Youtube video IDs from a given file path and regex dict

    @param path Path to the video links file
    @param rex List or tuple of regular expressions to use for searches
    @return List of Youtube video IDs found in the file
    """
    data = read_file(path)
    return extract_from(data, rex)


def read_file(path: str) -> list:
    """Read text links from the file at the given path

    Removes comments, including trailing comments, and empty lines.

    @param path Path to the text links file
    @return List of links found within the file
    """
    with open(path, "r") as fh:
        raw_data = fh.read().split("\n")

    # The file _should_ end with a single newline, but could be malformed
    if raw_data[-1] == "":
        raw_data = raw_data[:-1]

    # Trim whitespace on each line, if any
    data_trimmed = map(lambda x: x.strip(), raw_data)

    # Eliminate comment lines and empty lines
    data_reduced = functools.reduce(reduce_comment_empty, data_trimmed, [])

    # Eliminate trailing comments
    data_cleaned = list(map(remove_comment, data_reduced))

    return data_cleaned


def reduce_comment_empty(acc: list, crt: list) -> list:
    """Reduce text links data by removing comments and empty lines

    @param acc Accumulator list
    @param crt Current line to check
    @return If checks passed, accumulator with `crt` appended; otherwise,
    unchanged accumulator
    """
    if (not crt.startswith("#")) and (crt != ""):
        acc.append(crt)
    return acc


def reduce_result(acc: list, crt: str, rex: list) -> list:
    """Reduce a list of links based on regex searches

    Assumes regular expressions in the list will feature the `id` match group.

    @param acc Accumulator for storing results
    @param crt Current link string
    @param rex List or tuple of regular expressions
    @return If any match found, accumulator with matching ID appended;
    otherwise, unchanged accumulator
    """
    for r in rex:
        if (m := r.search(crt)) is not None:
            g = m.groupdict()
            if g.get("id", None) is None:
                raise RuntimeError("Regex missing `id` capture group")
            acc.append(g.get("id"))
            break
    return acc


def remove_comment(line: str) -> str:
    """Remove trailing comments in a line, if any

    @param line Line to check for trailing comments
    @return If comments found, line without comments; otherwise, unchanged line
    """
    # Check for spaces first, e.g. "text  # comment here"
    if len(spl := line.split(" ")) > 1:
        return spl[0]
    # Check for squashed comments, e.g. "text#comment"
    if len(spl := line.split("#")) > 1:
        return spl[0]
    # Return unchanged
    return line


# Class wrapper
# -----------------------------------------------------------------------------


class TextLinkParser:
    """Class-based wrapper for file contents"""

    _rex = REX_DEFAULT

    def __init__(self, path: str):
        self.path = path

    def extract(self) -> list:
        """Extract video IDs from the given path

        @return List of extracted video IDs
        """
        self.data = extract_from_file(self.path, self._rex)
        return self.data


# Main function
# -----------------------------------------------------------------------------


def main():
    """Print text links found to stdout, separated by newline

    Dummy / Testing operations
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file",
        metavar="FILE",
        type=str,
        help="Path to the video links text file")

    args = vars(parser.parse_args())

    data = extract_from_file(args.get("file"), REX_DEFAULT)

    if len(data) > 0:
        for d in data:
            print(d)


# Entrypoint
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
