"""Entry point for `sacamantecas` command line invocation."""
import atexit
from functools import partial
import sys

from legion import excepthook, wait_for_keypress

from sacamantecas import main, Messages

atexit.register(partial(wait_for_keypress, Messages.PRESS_ANY_KEY))
sys.excepthook = partial(excepthook, heading=Messages.UNHANDLED_EXCEPTION)
sys.exit(main(*sys.argv[1:]))
