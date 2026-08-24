import time

_START_TIME = time.time()


def get_uptime_seconds() -> int:
    return int(time.time() - _START_TIME)


def reset_uptime():
    global _START_TIME
    _START_TIME = time.time()
