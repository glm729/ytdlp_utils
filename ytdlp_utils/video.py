#!/usr/bin/env python3.10


# Class definition
# -----------------------------------------------------------------------------


class Video:
    """Class to collect and handle data for each video download"""

    _stage = {
        0: "Video",
        1: "Audio",
    }

    def __init__(self, video_id: str):
        self.already_downloaded = False
        self.dash_notified = False
        self.id = video_id
        self.progress = {
            0: 0.0,
            1: 0.0,
        }
        self.stage = None

    def get_stage_text(self, lower: bool = False) -> str:
        """Get the text representing the current stage

        @param lower Should the text be returned as lowercase?
        @return "Video" or "Audio", optionally lowercase
        """
        t = self._stage.get(self.stage)
        return t.lower() if lower else t

    def set_progress(self, percentage: float) -> None:
        """Set the progress for the current download stage

        Updates the progress according to the current download stage.

        @param percentage Percentage completion of the current download
        """
        self.progress.update({ self.stage: percentage, })

    def set_stage(self, stage: int) -> None:
        """Set the video download stage

        Stage must only be 0 or 1 -- video or audio.

        @param stage Download stage: 0 == video, 1 == audio
        """
        if not stage in [0, 1]:
            raise RuntimeError("Stage must only be 0 or 1")
        self.stage = stage
