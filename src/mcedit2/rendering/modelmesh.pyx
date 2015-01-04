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
from mcedit2.rendering cimport blockmodels

from libc.stdlib cimport malloc, realloc, free
from libc.string cimport memcpy

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
        cdef blockmodels.BlockModels blockModels

        cdef short cy = self.sectionUpdate.cy

        atlas = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas
        blockModels = atlas.blockModels
        blockModels.cookQuads(atlas)

        blocktypes = self.sectionUpdate.blocktypes
        areaBlocks = self.sectionUpdate.areaBlocks
        data = self.sectionUpdate.Data
        renderType = self.sectionUpdate.renderType
        opaqueCube = blocktypes.opaqueCube

        #faceQuadVerts = []

        cdef unsigned short y, z, x, ID, meta
        cdef short dx, dy, dz,
        cdef unsigned short nx, ny, nz, nID
        cdef blockmodels.ModelQuadList quads
        cdef blockmodels.ModelQuad quad

        cdef unsigned short rx, ry, rz

        cdef unsigned int buffer_ptr = 0
        cdef unsigned int buffer_size = 256
        cdef float * vertexBuffer = <float *>malloc(buffer_size * sizeof(float) * 24)
        cdef float * xyzuvc
        cdef numpy.ndarray vabuffer
        if vertexBuffer == NULL:
            return
        for y in range(1, 17):
            ry = y - 1 + (cy << 4)
            for z in range(1, 17):
                rz = z - 1
                for x in range(1, 17):
                    rx = x - 1
                    ID = areaBlocks[y, z, x]
                    if ID == 0:
                        continue
                    meta = data[y-1, z-1, x-1]

                    if renderType[ID] != 3:  # only model blocks for now
                        continue
                    quads = blockModels.cookedModelsByID[ID][meta]
                    if quads.count == 0:
                        continue

                    for i in range(quads.count):
                        quad = quads.quads[i]
                        if quad.cullface[0]:
                            nx = x + quad.cullface[1]
                            ny = y + quad.cullface[2]
                            nz = z + quad.cullface[3]
                            nID = areaBlocks[ny, nz, nx]
                            if opaqueCube[nID]:
                                continue

                        xyzuvc = vertexBuffer + buffer_ptr * 24
                        memcpy(xyzuvc, quad.xyzuvc, sizeof(float) * 24)

                        #(<object>verts).shape = 1, 4, 6
                        #verts[..., :3] += coords
                        xyzuvc[0] += rx
                        xyzuvc[1] += ry
                        xyzuvc[2] += rz
                        xyzuvc[6] += rx
                        xyzuvc[7] += ry
                        xyzuvc[8] += rz
                        xyzuvc[12] += rx
                        xyzuvc[13] += ry
                        xyzuvc[14] += rz
                        xyzuvc[18] += rx
                        xyzuvc[19] += ry
                        xyzuvc[20] += rz
                        buffer_ptr += 1
                        if buffer_ptr >= buffer_size:
                            buffer_size *= 2
                            vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * 24)
                            #buffer.resize((buffer_size, 24))
                        #faceQuadVerts.append(verts)

        if buffer_ptr:  # now buffer size
            vertexArray = VertexArrayBuffer(buffer_ptr, lights=False)
            vabuffer = vertexArray.buffer
            memcpy(vabuffer.data, vertexBuffer, buffer_ptr * sizeof(float) * 24)
            self.vertexArrays = [vertexArray]
        free(vertexBuffer)
