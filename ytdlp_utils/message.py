#!/usr/bin/env python3.8


# Class definition
# -----------------------------------------------------------------------------


class Message:

    _forms = {
        None:    " " * 7,
        "error": "\033[1;31mERROR:\033[0m ",
        "ok":    "\033[1;32mOK:\033[0m    ",
        "warn":  "\033[1;33mWARN:\033[0m  ",
        "info":  "\033[1;34mINFO:\033[0m  ",
        "input": "\033[1;35mINPUT:\033[0m ",
        "data":  "\033[1;36mDATA:\033[0m  ",
    }

    def __init__(self, text, form=None):
        self.text = text
        self.set_form(form)
        self.build()

    # ---- Public methods

    def build(self):
        self.message = f"{self._forms.get(self.form)}{self.text}"
        return self.message

    def print(self, **kwargs):
        self.build()
        print(self.message, **kwargs)

    def set_form(self, form):
        if form not in self._forms.keys():
            raise RuntimeError(f"No form found by key: {form}")
        self.form = form

    def set_text(self, text):
        self.text = text
