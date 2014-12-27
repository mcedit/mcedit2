"""
    geometrycache
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

import weakref

_caches = []

class GeometryCache(dict):

    def __init__(self, *a, **kwargs):
        super(GeometryCache, self).__init__(*a, **kwargs)
        _caches.append(weakref.ref(self))

def cache_stats():
    lines = []
    for c in _caches:
        c = c()
        if c is None:
            continue

        s = sum(a.size for a in c.itervalues())
        lines.append("%d kb" % (s / 1024))

    return "\n".join(lines)



