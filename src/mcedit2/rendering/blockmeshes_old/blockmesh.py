"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.layers import Layer
from mceditlib import faces

log = logging.getLogger(__name__)

directionOffsets = {
    faces.FaceXDecreasing: numpy.s_[1:-1, 1:-1, :-2],
    faces.FaceXIncreasing: numpy.s_[1:-1, 1:-1, 2:],
    faces.FaceYDecreasing: numpy.s_[:-2, 1:-1, 1:-1],
    faces.FaceYIncreasing: numpy.s_[2:, 1:-1, 1:-1],
    faces.FaceZDecreasing: numpy.s_[1:-1, :-2, 1:-1],
    faces.FaceZIncreasing: numpy.s_[1:-1, 2:, 1:-1],
}

class MeshBase(object):
    detailLevels = (0,)
    detailLevel = 0
    layer = Layer.Blocks
    renderType = NotImplemented
    extraTextures = ()
    renderstate = renderstates.RenderstateAlphaTestNode
    vertexArrays = ()

    def bufferSize(self):
        return sum(a.buffer.size for a in self.vertexArrays) * 4


class ChunkMeshBase(MeshBase):
    def __init__(self, chunkUpdate):
        """

        :type chunkUpdate: ChunkUpdate
        """
        self.chunkUpdate = chunkUpdate
        self.vertexArrays = []

class BlockMeshBase(MeshBase):

    def __init__(self, sectionUpdate):
        """

        :type sectionUpdate: SectionUpdate
        """
        self.sectionUpdate = sectionUpdate
        self.vertexArrays = []

    def getRenderTypeMask(self):
        return self.sectionUpdate.blockRenderTypes == self.renderType

    def facingBlockLights(self, direction):
        return self.sectionUpdate.areaBlockLights[directionOffsets[direction]]

    def facingSkyLights(self, direction):
        return self.sectionUpdate.areaSkyLights[directionOffsets[direction]]

    def makeVertices(self):
        yield
        arrays = []
        renderTypeMask = self.getRenderTypeMask()
        yield

        for (direction, exposedFaceMask) in enumerate(self.sectionUpdate.exposedBlockMasks):
            vertexBuffer = self.makeFaceVertices(direction, renderTypeMask, exposedFaceMask)
            yield
            if len(vertexBuffer):
                arrays.append(vertexBuffer)
        self.vertexArrays = arrays

    makeFaceVertices = NotImplemented
