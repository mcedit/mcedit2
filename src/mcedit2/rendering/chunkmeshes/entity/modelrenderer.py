"""
    modelrenderer
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import collections
import logging

log = logging.getLogger(__name__)


class ModelBox(collections.namedtuple(
    'ModelBox',
    'u v x y z w h l expandOffset mirror',
)):

    @property
    def x2(self):
        return self.x + self.w

    @property
    def y2(self):
        return self.y + self.h

    @property
    def z2(self):
        return self.z + self.l

    @property
    def dx(self):
        return self.w

    @property
    def dy(self):
        return self.h

    @property
    def dz(self):
        return self.l


class ModelRenderer(object):
    def __init__(self, parent, u=0, v=0):
        self.parent = parent
        self.boxes = []
        self.u = u
        self.v = v
        self.mirror = False
        self.cx, self.cy, self.cz = 0, 0, 0
        self.rx, self.ry, self.rz = 0, 0, 0

    def addBox(self, x, y, z, w, h, l, expandOffset=0.0, mirror=None):
        if mirror is None:
            mirror = self.mirror
        self.boxes.append(ModelBox(self.u, self.v, x, y, z, w, h, l, expandOffset, mirror))

    def setCenterPoint(self, x, y, z):
        self.cx, self.cy, self.cz = x, y, z

    def setRotation(self, rx, ry, rz):
        self.rx, self.ry, self.rz = rx, ry, rz

    def setTextureOffset(self, u, v):
        self.u, self.v = u, v
