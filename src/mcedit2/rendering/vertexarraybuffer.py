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
    def __init__(self, shape, gl_type, textures=True, lights=True):
        """
        Vertex buffer, stores an array of `shape` vertexes with a number of elements per vertex
        determined by textures and lights. Also stores a gl_type such as GL.GL_QUADS that will
        be passed to glDrawArrays when drawing the array buffer (perhaps doesn't belong here? xxx)

        Shape is a value or a tuple of values that defines the number of vertexes. Shape is similar
        to a numpy array's shape and defines the shape of the underlying buffer array.

        Element types:

            vertex:
                x: float32
                y: float32
                z: float32
            texcoord:
                s: float32 (with textures=True)
                t: float32 (with textures=True)
            lightcoord:
                bl: float32 (with lights=True)
                sl: float32 (with lights=True)
            rgba:
                rgba: uint8 (four uint8s packed with r in the most significant byte)


        Access elements using .vertex, .texcoord, .lightcoord, .rgba

        :type shape: int | tuple[int]
        :type textures: bool
        :type lights: bool
        :return:
        :rtype: VertexArrayBuffer
        """
        if not isinstance(shape, tuple):
            shape = (shape,)

        self.elements = 4
        if textures:
            self.texOffset = self.elements - 1
            self.elements += 2
        if lights:
            self.lightOffset = self.elements - 1
            self.elements += 2
        self.rgbaOffset = self.elements - 1

        self.shape = shape
        self.buffer = numpy.zeros(shape + (self.elements,), dtype='f4')
        self.gl_type = gl_type
        self.lights = lights
        self.textures = textures
        self.rgba[:] = 0xff

    def copy(self):
        copy = VertexArrayBuffer(self.shape, self.gl_type, self.textures, self.lights)
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


class QuadVertexArrayBuffer(VertexArrayBuffer):

    def __init__(self, count, textures=True, lights=True):
        """
        VertexArrayBuffer subclass specialized to store an array of quads. Initalizes an array
        with shape=(count, 4) and provides a `fromBlockMask` method to create an array with
        x,y,z elements taken from the positions of the True values in a 3D mask array.

        :param count:
        :type count:
        :param textures:
        :type textures:
        :param lights:
        :type lights:
        :return:
        :rtype:
        """
        super(QuadVertexArrayBuffer, self).__init__((count, 4), GL.GL_QUADS, textures, lights)

    @classmethod
    def fromBlockMask(cls, face, blockMask, textures=True, lights=True):
        """
        Create a vertex array using a face direction and a 3D mask array (ordered y,z,x as
        in ChunkSection arrays). The array's x, y, z elements are initialized to the corners
        of a quad facing the indicated direction and in the position of each True value in the mask array.

        This was used a lot for the pre-model block rendering and it may still come in handy.

        :param face:
        :type face:
        :param blockMask:
        :type blockMask:
        :param textures:
        :type textures:
        :param lights:
        :type lights:
        :return:
        :rtype: QuadVertexArrayBuffer
        """

        y, z, x = blockMask.nonzero()
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

