#!/usr/bin/env python3.10


# Class definition
# -----------------------------------------------------------------------------


class Status:
    """Collect data relating to the status of an item"""

    def __init__(self, prefix: str, header: str, body: str):
        self.update({
            "prefix": prefix,
            "header": header,
            "body": body,
        })

    def _build(self) -> None:
        """Build the status text

        Currently does not handle missing attributes.
        """
        self.status = "{p} {h} {b}".format(
            p=self.prefix,
            h=self.header,
            b=self.body)

    def update(self, data: dict) -> None:
        """Update the status data

        Builds the text after assignments.

        @param data Dict of data to use for updating status
        """
        for (k, v) in data.items():
            if not k in ["prefix", "header", "body"]:
                continue
            setattr(self, k, v)
        self._build()

