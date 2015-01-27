#cython: boundscheck=False
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
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaBlockLight
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaSkyLight
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
        areaBlockLight = self.sectionUpdate.areaLights("BlockLight")
        areaSkyLight = self.sectionUpdate.areaLights("SkyLight")
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
        cdef unsigned char bl, sl

        cdef size_t buffer_ptr = 0
        cdef size_t buffer_size = 256
        cdef float * vertexBuffer = <float *>malloc(buffer_size * sizeof(float) * 32)
        cdef float * xyzuvstc
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

                        nx = x + quad.quadface[1]
                        ny = y + quad.quadface[2]
                        nz = z + quad.quadface[3]
                        bl = areaBlockLight[ny, nz, nx]
                        sl = areaSkyLight[ny, nz, nx]


                        xyzuvstc = vertexBuffer + buffer_ptr * 32
                        memcpy(xyzuvstc, quad.xyzuvstc, sizeof(float) * 32)

                        xyzuvstc[0] += rx
                        xyzuvstc[1] += ry
                        xyzuvstc[2] += rz
                        xyzuvstc[5] += bl
                        xyzuvstc[6] += sl


                        xyzuvstc[8] += rx
                        xyzuvstc[9] += ry
                        xyzuvstc[10] += rz
                        xyzuvstc[13] += bl
                        xyzuvstc[14] += sl


                        xyzuvstc[16] += rx
                        xyzuvstc[17] += ry
                        xyzuvstc[18] += rz
                        xyzuvstc[21] += bl
                        xyzuvstc[22] += sl


                        xyzuvstc[24] += rx
                        xyzuvstc[25] += ry
                        xyzuvstc[26] += rz
                        xyzuvstc[29] += bl
                        xyzuvstc[30] += sl

                        buffer_ptr += 1
                        if buffer_ptr >= buffer_size:
                            buffer_size *= 2
                            vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * 32)

        if buffer_ptr:  # now buffer size
            vertexArray = VertexArrayBuffer(buffer_ptr)
            vabuffer = vertexArray.buffer
            memcpy(vabuffer.data, vertexBuffer, buffer_ptr * sizeof(float) * 32)
            self.vertexArrays = [vertexArray]
        free(vertexBuffer)
