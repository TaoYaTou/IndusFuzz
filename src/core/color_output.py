import sys
import os

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"

_COLOR_ENABLED = None


def _detect_color():
    global _COLOR_ENABLED
    if _COLOR_ENABLED is not None:
        return _COLOR_ENABLED
    if os.environ.get("NO_COLOR"):
        _COLOR_ENABLED = False
        return _COLOR_ENABLED
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        _COLOR_ENABLED = False
        return _COLOR_ENABLED
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hStdOut = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode)):
                kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004)
                _COLOR_ENABLED = True
            else:
                _COLOR_ENABLED = False
        except Exception:
            _COLOR_ENABLED = False
    else:
        _COLOR_ENABLED = True
    return _COLOR_ENABLED


def _wrap(color, text):
    if not _detect_color():
        return text
    return f"{color}{text}{RESET}"


def print_ok(msg):
    print(_wrap(GREEN, msg))


def print_warn(msg):
    print(_wrap(YELLOW, msg))


def print_error(msg):
    print(_wrap(RED, msg))


def print_info(msg):
    print(_wrap(CYAN, msg))


def print_risk(msg, level):
    level = str(level).upper()
    if level == "HIGH":
        print(_wrap(BOLD + RED, msg))
    elif level == "MEDIUM":
        print(_wrap(YELLOW, msg))
    else:
        print(_wrap(GREEN, msg))
