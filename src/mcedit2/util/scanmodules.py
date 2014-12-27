"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from importlib import import_module
import logging
import os
import pkgutil

log = logging.getLogger(__name__)


def ScanModules(modulename, path):
    log.info("Scanning %s (%s)", modulename, path)
    for _, name, _ in pkgutil.iter_modules([os.path.dirname(path)]):
        log.debug("Found %s.%s", modulename, name)
        try:
            yield import_module(modulename + "." + name)
        except ImportError as e:
            log.exception("Failed to import %s from %s (%s): %s", name, path, modulename, e)
