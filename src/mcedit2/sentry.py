from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from raven import Client, breadcrumbs

_client = None

def get_sentry_client():
    global _client
    if _client is None:
        from mcedit2 import __version__

        _client = Client('https://76ebd10b53b841fe8ec9d928f12671e1:d33c89b4955c41338b0deb96dc7be78f@sentry.io/184596',
                         install_sys_hook=False,
                         release=__version__)
        breadcrumbs.register_logging_handler(_log_handler)
    return _client

def _log_handler(logger, level, *a):
    return level <= logging.DEBUG