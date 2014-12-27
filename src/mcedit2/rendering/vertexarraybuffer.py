"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
import numpy
from mcedit2.rendering.slices import _XYZ, _ST, _SLBL, _RGBA, _RGB, _A

log = logging.getLogger(__name__)


class VertexArrayBuffer(object):

    def __init__(self, count, textures=True, lights=True):
        """
        Vertex buffer, stores an array of `count` quad vertexes with a number of elements determined by textures and
        lights.
        Access elements using .vertex, .texcoord, .lightcoord, .rgba

        :type count: int
        :type textures: bool
        :type lights: bool
        :return:
        :rtype: VertexArrayBuffer
        """
        self.elements = 4
        if textures:
            self.elements += 2
        if lights:
            self.elements += 2

        self.buffer = numpy.zeros((count, 4, self.elements), dtype='f4')
        self.gl_type = GL.GL_QUADS
        self.lights = lights
        self.textures = textures
        self.rgba[:] = 0xff

    @classmethod
    def fromIndices(cls, direction, blockIndices, textures=True, lights=True):
        """

        :param direction:
        :type direction:
        :param blockIndices:
        :type blockIndices:
        :param textures:
        :type textures:
        :param lights:
        :type lights:
        :return:
        :rtype: VertexArrayBuffer
        """
        y, z, x = blockIndices.nonzero()
        vertexBuffer = cls(len(x), textures, lights)
        if len(x) == 0:
            return vertexBuffer

        vertexBuffer.vertex[..., 0] = x[..., None]
        vertexBuffer.vertex[..., 1] = y[..., None]
        vertexBuffer.vertex[..., 2] = z[..., None]
        #vertexBuffer.vertex[:] += standardCubeTemplates[direction, ..., 0:3]
        #if textures:
        #    vertexBuffer.texcoord[:] = standardCubeTemplates[direction, ..., 3:5]
        if lights:
            vertexBuffer.lightcoord[:] = [[[0.5, 0.5]]]

        return vertexBuffer

    def copy(self):
        copy = VertexArrayBuffer(len(self.buffer), self.textures, self.lights)
        copy.buffer[:] = self.buffer
        return copy

    def setLights(self, skyLight, blockLight):
        assert self.lights
        self.lightcoord[..., 0] += skyLight[..., None]
        self.lightcoord[..., 1] += blockLight[..., None]

    def applyTexMap(self, ltwh):
        assert self.textures
        self.texcoord[:] *= ltwh[..., None, 2:4]
        self.texcoord[:] += ltwh[..., None, 0:2]

    @property
    def vertex(self):
        return self.buffer[_XYZ]

    @property
    def texcoord(self):
        return self.buffer[_ST]

    @property
    def lightcoord(self):
        return self.buffer[_SLBL]

    @property
    def rgba(self):
        return self.buffer.view('uint8')[_RGBA]

    @property
    def rgb(self):
        return self.buffer.view('uint8')[_RGB]

    @property
    def alpha(self):
        return self.buffer.view('uint8')[_A]

    def __len__(self):
        return len(self.buffer)

