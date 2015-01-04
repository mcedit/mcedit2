#cython: boundscheck=False, profile=True
"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging

import numpy
cimport numpy

from mcedit2.rendering import renderstates
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)


class BlockModelMesh(object):
    renderstate = renderstates.RenderstateAlphaTestNode
    def __init__(self, sectionUpdate):
        """

        :param sectionUpdate:
        :type sectionUpdate: mcedit2.rendering.chunkupdate.SectionUpdate
        :return:
        :rtype:
        """
        self.sectionUpdate = sectionUpdate
        self.vertexArrays = []

    def createVertexArrays(self):
        cdef numpy.ndarray[numpy.uint16_t, ndim=3] areaBlocks
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] data
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] renderType
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] opaqueCube

        chunk = self.sectionUpdate.chunkUpdate.chunk
        cdef short cy = self.sectionUpdate.cy
        section = chunk.getSection(cy)
        if section is None:
            return

        atlas = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas
        blockModels = atlas.blockModels
        blockModels.cookQuads(atlas)

        blocktypes = self.sectionUpdate.blocktypes
        areaBlocks = self.sectionUpdate.areaBlocks
        data = section.Data
        renderType = self.sectionUpdate.renderType
        opaqueCube = blocktypes.opaqueCube

        faceQuadVerts = []

        cdef unsigned short y, z, x, ID, meta
        cdef short dx, dy, dz,
        cdef unsigned short nx, ny, nz, nID
        cdef numpy.ndarray verts
        cdef list quads
        cdef tuple quad

        cdef numpy.ndarray[numpy.uint16_t, ndim=1] coords = numpy.zeros(3, dtype=numpy.uint16)
        cdef numpy.ndarray[list, ndim=2] cookedModelsByID = blockModels.cookedModelsByID

        for y in range(1, 17):
            coords[1] = y - 1 + (cy << 4)
            for z in range(1, 17):
                coords[2] = z - 1
                for x in range(1, 17):
                    coords[0] = x - 1
                    ID = areaBlocks[y, z, x]
                    if ID == 0:
                        continue
                    meta = data[y-1, z-1, x-1]

                    if renderType[ID] != 3:  # only model blocks for now
                        continue
                    quads = cookedModelsByID[ID, meta]
                    if quads is None:
                        continue

                    for xyzuvc, cullface in quads:
                        if cullface is not None:
                            dx, dy, dz = cullface.vector
                            nx = x + dx
                            ny = y + dy
                            nz = z + dz
                            nID = areaBlocks[ny, nz, nx]
                            if opaqueCube[nID]:
                                continue

                        verts = numpy.array(xyzuvc)
                        verts[..., :3] += coords
                        faceQuadVerts.append(verts)
                        # log.info("Block %s:\nVertices: %s", (x-1, y-1, z-1), verts)

        # raise SystemExit
        if len(faceQuadVerts):
            vertexArray = VertexArrayBuffer(len(faceQuadVerts), lights=False)
            vertexArray.buffer[..., :6] = numpy.vstack(faceQuadVerts)
            self.vertexArrays = [vertexArray]
