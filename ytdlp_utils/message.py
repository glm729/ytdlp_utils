# Class definition
# -----------------------------------------------------------------------------


class Message:

    _forms = {
        None:    " " * 7,
        "error": "\x1b[1;31mERROR:\x1b[0m ",
        "ok":    "\x1b[1;32mOK:\x1b[0m    ",
        "warn":  "\x1b[1;33mWARN:\x1b[0m  ",
        "info":  "\x1b[1;34mINFO:\x1b[0m  ",
        "input": "\x1b[1;35mINPUT:\x1b[0m ",
        "data":  "\x1b[1;36mDATA:\x1b[0m  ",
    }

    def __init__(self, text, form=None):
        self.text = text
        self.set_form(form)
        self.build()

    # ---- Private methods ----

    def _get_form_text(self):
        """Shorthand helper to get the message form text"""
        self._forms.get(self.form)

    # ---- Public methods ----

    def build(self):
        """Build the message text

        Prepares a formatted string using the message form text and the message
        text.  Returns the constructed message.
        """
        self.message = "{form}{text}".format(
            form=self._get_form_text(),
            text=self.text)
        return self.message

    def print(self, **kwargs):
        """Build and print the message text

        Passes kwargs to ``print``.
        """
        self.build()
        print(self.message, **kwargs)

    def set_form(self, form: str = None):
        """Set the form of the message

        Throws a ``ValueError`` if the form key does not exist.

        :param str form: Message form
        """
        if form not in self._forms:
            raise ValueError(f"No message form found by key: {form}")
        self.form = form
