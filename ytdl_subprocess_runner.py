#!/usr/bin/env python3.8


# Module imports
# -----------------------------------------------------------------------------


import queue
import re
import subprocess
import threading
import time

from _modules.message import Message


# Class definition
# -----------------------------------------------------------------------------


class YtdlSubprocessRunner:

    _ok = True

    _restart = True

    _opt = {
        "format": "/".join((
            "298+bestaudio",
            "136+bestaudio",
            "22",
            "bestvideo[height=720][fps=60]+bestaudio",
            "bestvideo[height=720][fps=30]+bestaudio",
            "bestvideo[height<=480]+bestaudio")),
        "output": "%(uploader)s/%(title)s.%(ext)s"
    }

    _rex = {
        "merging": re.compile(r"^\[Merger\] Merging formats into"),
        "progress": re.compile(''.join((
            r"^\[download\] +",
            r"(?P<pc>\d+\.\d)%",
            r" of \d+\.\d+[KM]iB at +",
            r"(?P<sp>\d+\.\d+[KM])iB\/s"))),
        "stage": re.compile(r"^\[download\] Destination:")
    }

    def __init__(self, video_id, slow_count=30, restart_count=10):
        self._store_data(video_id)
        self.slow_count = slow_count
        self.restart_count = restart_count

    # ---- Public methods

    def run(self):
        self._init_mq()
        self._message("Starting download", "ok")
        self._time_start = time.time()
        while self._restart:
            self._new_process()
            self._wait()
        time_end = time.time() - self._time_start
        if self._ok:
            t = f"Video downloaded and merged in {time_end:.1f}s"
            f = "ok"
        else:
            t = f"Video download failed after {time_end:.1f}s"
            f = "error"
        self._message(t, f)
        self._close_mq()

    # ---- Private methods ----

    def _build_cmd(self):
        return (
            "yt-dlp",
            "--force-ipv4",
            "--geo-bypass",
            "--newline",
            "--format",
            self._opt.get("format"),
            "--output",
            self._opt.get("output"),
            f"https://www.youtube.com/watch?v={self._id}")

    def _check_line_stderr(self, stderr):
        while (l := stderr.readline()):
            line = l.decode("utf-8").strip()
            #=> DEBUG
            # t = f"\n{' ' * 7}".join(("STDERR:", line))
            # self._message(t, "warn")
            #<=
            if line.endswith("HTTP Error 403: Forbidden"):
                self._restart(cause="403")
                continue

    def _check_line_stdout(self, stdout, time_start):
        while (l := stdout.readline()):
            line = l.decode("utf-8").strip()
            check_merging = self._rex["merging"].search(line)
            check_stage = self._rex["stage"].search(line)
            check_progress = self._rex["progress"].search(line)
            if check_merging is not None:
                self._message("Merging data", "info")
                continue
            if check_stage is not None:
                if self._stage == "start":
                    self._stage = "Video"
                    self._message("Downloading video", "info")
                elif self._stage == "Video":
                    self._stage = "Audio"
                    self.data.update({ "progress": 0 })
                    self._message("Downloading audio", "info")
                continue
            if check_progress is not None:
                data = check_progress.groupdict()
                if (p := data.get("pc", None)) is not None:
                    self._check_percentage(p, time_start)
                if (s := data.get("sp", None)) is not None:
                    self._check_speed(s)

    def _check_percentage(self, percentage, time_start):
        pc = int(percentage.split(".")[0])
        if pc >= (p := self.data.get("progress") + 20):
            self.data.update({ "progress": p })
            tn = time.time() - time_start
            w = " " * (4 - len(str(p)))
            t = f"{self._stage} download reached {p}%{w}({tn:.1f}s)"
            self._message(t, "info")

    def _check_speed(self, speed):
        if speed.endswith("K"):
            update_value = self.data.get("slow_count") + 1
            if update_value > self.slow_count:
                self._restart(cause="slow")
                return
        else:
            update_value = 0
        self.data.update({ "slow_count": update_value })

    def _close_mq(self):
        self._running = False
        self._q_msg.join()
        self._t_msg.join()

    def _fun_t_msg(self):
        while self._running:
            try:
                task = self._q_msg.get(timeout=0.2)
                self._print(Message(task[0], form=task[1]))
                self._q_msg.task_done()
            except queue.Empty:
                pass

    def _init_mq(self):
        self._running = True
        self._lock = threading.RLock()
        self._q_msg = queue.Queue()
        self._t_msg = threading.Thread(
            target=self._fun_t_msg,
            daemon=True)
        self._t_msg.start()

    def _join_threads(self):
        self._stdout_thread.join()
        self._stderr_thread.join()

    def _message(self, t, f):
        self._lock.acquire()
        try:
            self._q_msg.put((f"{self._id}: {t}", f))
        finally:
            self._lock.release()

    def _new_process(self):
        self._stage = "start"
        self._proc = subprocess.Popen(
            self._build_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self._stdout_thread = threading.Thread(
            target=self._check_line_stdout,
            args=(self._proc.stdout, self._time_start),
            daemon=True)
        self._stderr_thread = threading.Thread(
            target=self._check_line_stderr,
            args=(self._proc.stderr,),
            daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _print(self, m):
        self._lock.acquire()
        try:
            m.print()
        finally:
            self._lock.release()

    def _restart(self, cause="slow"):
        self._proc.kill()
        rsc = self.data.get("restart_count") + 1
        if rsc > self.restart_count:
            self._ok = False
            self._restart = False
            self._message("Restart limit reached", "warn")
            return
        if cause == "slow":
            t = " ".join((
                "Reached slow speed limit, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            self._message(t, "warn")
        elif cause == "403":
            t = " ".join((
                f"Received HTTP Error 403, restarting",
                f"(remaining: {self.restart_count - rsc})"))
            self._message(t, "warn")
        self.data.update({ "restart_count": rsc, "slow_count": 0 })

    def _store_data(self, video_id):
        self._id = video_id
        self.data = {
            "id": video_id,
            "progress": 0,
            "restart_count": 0,
            "slow_count": 0
        }

    def _wait(self):
        self._proc.wait()
        self._join_threads()
        if self._proc.returncode == 0:
            self._restart = False


# Operations
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys
    sp_runner = YtdlSubprocessRunner(sys.argv[1])
    sp_runner.run()
