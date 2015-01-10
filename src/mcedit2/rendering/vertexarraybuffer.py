"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
import numpy
from mcedit2.rendering.blockmeshes import standardCubeTemplates

log = logging.getLogger(__name__)


class VertexArrayBuffer(object):
    texOffset = None
    lightOffset = None
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
            self.texOffset = self.elements - 1
            self.elements += 2
        if lights:
            self.lightOffset = self.elements - 1
            self.elements += 2
        self.rgbaOffset = self.elements - 1

        self.buffer = numpy.zeros((count, 4, self.elements), dtype='f4')
        self.gl_type = GL.GL_QUADS
        self.lights = lights
        self.textures = textures
        self.rgba[:] = 0xff

    @classmethod
    def fromIndices(cls, face, blockIndices, textures=True, lights=True):
        """

        :param face:
        :type face:
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
        vertexBuffer.vertex[:] += standardCubeTemplates[face, ..., 0:3]

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
        return self.buffer[..., :3]

    @property
    def texcoord(self):
        return self.buffer[..., self.texOffset:self.texOffset+2]

    @property
    def lightcoord(self):
        return self.buffer[..., self.lightOffset:self.lightOffset+2]

    @property
    def rgba(self):
        return self.buffer.view('uint8')[..., self.rgbaOffset*4:self.rgbaOffset*4+4]

    @property
    def rgb(self):
        return self.buffer.view('uint8')[..., self.rgbaOffset*4:self.rgbaOffset*4+3]

    @property
    def alpha(self):
        return self.buffer.view('uint8')[..., self.rgbaOffset*4+3:self.rgbaOffset*4+4]

    def __len__(self):
        return len(self.buffer)

