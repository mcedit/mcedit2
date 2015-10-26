"""
    transforms
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import weakref

log = logging.getLogger(__name__)


class SceneNodeState(object):
    def __init__(self):
        self._parents = []

    def addParent(self, parent):
        self._parents.append(weakref.ref(parent))

    def removeParent(self, parent):
        self._parents = [p for p in self._parents if p() and p() != parent]

    _dirty = False

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        self._dirty = value
        if value:
            for p in self._parents:
                p = p()
                if p:
                    p.dirty = True

    def enter(self):
        raise NotImplementedError

    def exit(self):
        raise NotImplementedError

    def compile(self):
        pass

