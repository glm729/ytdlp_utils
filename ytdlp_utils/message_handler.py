#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import threading

from message import Message


# Class definition
# -----------------------------------------------------------------------------


class MessageHandler:

    def __init__(self):
        pass

    # ---- Public methods

    def end(self) -> None:
        """End message handler operations"""
        self._queue.join()
        self._loop = False
        self._thread.join()

    def message(self, text: str, form: str) -> None:
        """Enqueue a message to print

        @param text Message text.
        @param form Message form.
        """
        self._enqueue_message(Message(text=text, form=form))

    def start(self) -> None:
        """Start message handler operations"""
        self._loop = True
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._fun_thread, daemon=True)
        self._thread.start()

    # ---- Private methods

    def _enqueue_message(self, message: Message) -> None:
        """Wrap enqueuing a message in a recursive lock

        @param message Message object to enqueue.
        """
        self._lock.acquire()
        try:
            self._queue.put(message)
        finally:
            self._lock.release()

    def _fun_thread(self) -> None:
        """Message thread target function"""
        while self._loop:
            try:
                self._print(self._queue.get(timeout=0.2))
                self._queue.task_done()
            except queue.Empty:
                pass

    def _print(self, message: Message) -> None:
        """Wrap message printing in a recursive lock

        @param message Message object to print.
        """
        self._lock.acquire()
        try:
            message.print()
        finally:
            self._lock.release()
