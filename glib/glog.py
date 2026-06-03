"""
Simple logger for MicroPython.

Usage:
    from glib.glog import Logger
    log = Logger(level=2)   # 1=errors only, 2=info+errors, 3=debug+all
    log.error("something broke")
    log.info("connected")
    log.debug("raw value: 42")
"""


class Logger:

    LEVELS = {"ERROR": 1, "INFO": 2, "DEBUG": 3}

    def __init__(self, level=2):
        self.current_level = level

    def setLevel(self, level):
        self.current_level = level

    def log(self, message, level="INFO"):
        if self.LEVELS[level] <= self.current_level:
            print(f"{level}: {message}")

    def error(self, message):
        self.log(message, "ERROR")

    def info(self, message):
        self.log(message, "INFO")

    def debug(self, message):
        self.log(message, "DEBUG")
