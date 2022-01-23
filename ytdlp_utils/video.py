#!/usr/bin/env python3.8


# Class definition
# -----------------------------------------------------------------------------


class Video:

    _dash_notified = False

    _prefix_template = "\033[1;{colour}m{video_id}\033[0m"

    _stage_text = {
        0: "Video",
        1: "Audio",
    }

    def __init__(self, video_id: str, colour_index: int = 37):
        self.already_downloaded = False
        self.count_restart = 0
        self.count_slow = 0
        self.id = video_id
        self.progress = 0
        self.stage = 0
        self.time_start = None
        self._make_prefix(colour_index)

    # ---- Public methods

    def decrement_stage(self) -> None:
        """Decrement the instance download stage

        Guards against negative stages by setting to 0 if already at or below
        0.  The below-zero part may seem strange, but I've seen it happen
        somehow, probably to do with unlocked thread operations.
        """
        if self.stage <= 0:
            self.stage = 0
            return
        self.stage -= 1

    def get_stage(self, lower: bool = False) -> str:
        """Return text for the current stage

        @param lower Return the text as lowercase?
        @return Text informing of the current stage; capitalised or lowercase.
        """
        t = self._stage_text.get(self.stage, "Unknown stage")
        if lower:
            return t.lower()
        return t

    def increment_stage(self) -> None:
        """Increment the instance download stage

        Guards against excess stages by setting to 3 if already at or above 3.
        This may seem strange, but I've seen stages as high as 7 or 8 between
        checks somehow, probably from unlocked thread operations.
        """
        self.progress = 0
        if self.stage >= 3:
            self.stage = 3
            return
        self.stage += 1

    # ---- Private methods

    def _make_prefix(self, colour_index: int) -> None:
        """Set the prefix for the instance

        @param colour_index Shell escape colour to use for prefix text
        colouring.
        """
        self.prefix = self._prefix_template.format(
            colour=str(colour_index),
            video_id=self.id)
