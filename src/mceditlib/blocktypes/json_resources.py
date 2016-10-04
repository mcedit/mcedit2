"""
    json_resources
"""
from __future__ import absolute_import, division, print_function
import json
import logging
import os
from os.path import join
import traceback

log = logging.getLogger(__name__)

_cachedJsons = {}

def openResource(filename):
    path = join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        try:
            # py2exe, .egg
            import pkg_resources
            return pkg_resources.resource_stream(__name__, filename)
        except ImportError as e:
            log.exception("pkg_resources not available")
            raise

    return open(path)

def getJsonFile(filename):
    if filename in _cachedJsons:
        return _cachedJsons[filename]

    f = openResource(filename)
    try:
        s = f.read()
        entries = json.loads(s)
        _cachedJsons[filename] = entries
        return entries
    except EnvironmentError as e:
        log.error(u"Exception while loading JSON from %s: %s", f, e)
        traceback.print_exc()
