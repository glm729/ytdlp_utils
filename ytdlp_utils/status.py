#!/usr/bin/env python3.10


# Class definition
# -----------------------------------------------------------------------------


class Status:
    """Collect data relating to the status of an item"""

    _accept_keys = ["prefix", "header", "body"]

    def __init__(self, data):
        self.update(data)

    def _build(self) -> None:
        """Build the status text

        Gets all data per acceptable key, and eliminates values which are None.
        Joins remainder separated by a single space.
        """
        to_use = map(lambda x: getattr(self, x, None), self._accept_keys)
        to_use = filter(lambda x: x is not None, to_use)
        self.status = " ".join(to_use)

    def update(self, data: dict) -> None:
        """Update the status data

        Builds the text after assignments.

        @param data Dict of data to use for updating status
        """
        for (k, v) in data.items():
            if not k in self._accept_keys:
                continue
            setattr(self, k, v)
        self._build()
