#cython: boundscheck=False
"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging

import numpy
cimport numpy

from mcedit2.rendering import renderstates, scenegraph
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
cimport mcedit2.rendering.blockmodels as blockmodels

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
        self.sceneNode = None
        self.layer = Layer.Blocks

    def createVertexArrays(self):
        DEF quadFloats = 32
        DEF vertexBytes = 32
        cdef numpy.ndarray[numpy.uint16_t, ndim=3] areaBlocks
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaBlockLight
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaSkyLight
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaData
        cdef numpy.ndarray[numpy.uint8_t, ndim=2] areaBiomes
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] renderType
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] opaqueCube
        cdef numpy.ndarray[numpy.float32_t, ndim=1] biomeTemp
        cdef numpy.ndarray[numpy.float32_t, ndim=1] biomeRain

        cdef blockmodels.BlockModels blockModels

        cdef short cy = self.sectionUpdate.cy

        atlas = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas
        blockModels = atlas.blockModels
        if not blockModels.cooked:
            log.warn("createVertexArrays: Block models not cooked, aborting.")
            return

        blocktypes = self.sectionUpdate.blocktypes
        areaBlocks = self.sectionUpdate.areaBlocks
        areaBlockLight = self.sectionUpdate.areaLights("BlockLight")
        areaSkyLight = self.sectionUpdate.areaLights("SkyLight")
        areaData = self.sectionUpdate.areaData
        areaBiomes = self.sectionUpdate.areaBiomes
        renderType = self.sectionUpdate.renderType
        opaqueCube = blocktypes.opaqueCube
        biomeTemp = self.sectionUpdate.biomeTemp
        biomeRain = self.sectionUpdate.biomeRain



        #faceQuadVerts = []
        cdef unsigned short waterID = blocktypes["minecraft:water"].ID
        cdef unsigned short waterFlowID = blocktypes["minecraft:flowing_water"].ID
        cdef unsigned short lavaID = blocktypes["minecraft:lava"].ID
        cdef unsigned short lavaFlowID = blocktypes["minecraft:flowing_lava"].ID
        waterTexTuple = self.sectionUpdate.chunkUpdate.textureAtlas.texCoordsByName["assets/minecraft/textures/blocks/water_still.png"]
        cdef float[4] waterTex
        waterTex[0] = waterTexTuple[0]
        waterTex[1] = waterTexTuple[1]
        waterTex[2] = waterTexTuple[2]
        waterTex[3] = waterTexTuple[3]
        lavaTexTuple = self.sectionUpdate.chunkUpdate.textureAtlas.texCoordsByName["assets/minecraft/textures/blocks/lava_still.png"]
        cdef float[4] lavaTex
        lavaTex[0] = lavaTexTuple[0]
        lavaTex[1] = lavaTexTuple[1]
        lavaTex[2] = lavaTexTuple[2]
        lavaTex[3] = lavaTexTuple[3]

        cdef float * fluidTex

        cdef unsigned short y, z, x, ID, meta
        cdef short dx, dy, dz,
        cdef unsigned short nx, ny, nz, nID, upID
        cdef unsigned char nMeta
        cdef blockmodels.ModelQuadList quads
        cdef blockmodels.ModelQuad quad

        cdef short rx, ry, rz
        cdef unsigned char bl, sl
        cdef unsigned char tintType
        cdef unsigned char biomeID
        cdef float temperature, rainfall
        cdef unsigned int imageX, imageY
        cdef size_t imageOffset

        cdef size_t buffer_ptr = 0
        cdef size_t buffer_size = 256
        cdef float * vertexBuffer = <float *>malloc(buffer_size * sizeof(float) * quadFloats)
        cdef float * xyzuvstc
        cdef numpy.ndarray vabuffer
        cdef unsigned char * vertexColor
        cdef unsigned short color
        cdef size_t vertex, channel
        cdef const unsigned char * tintColor

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
                    meta = areaData[y, z, x]

                    if renderType[ID] == 3:  # model blocks
                        quads = blockModels.cookedModelsByID[ID][meta]
                        if quads.count == 0:
                            continue

                        biomeID = areaBiomes[z, x]

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
                            bl = areaBlockLight[ny, nz, nx]  # xxx block.useNeighborLighting
                            sl = areaSkyLight[ny, nz, nx]

                            xyzuvstc = vertexBuffer + buffer_ptr * quadFloats
                            memcpy(xyzuvstc, quad.xyzuvstc, sizeof(float) * quadFloats)

                            temperature = biomeTemp[biomeID]
                            rainfall = biomeRain[biomeID]
                            temperature = min(max(temperature, 0.0), 1.0)
                            rainfall = min(max(rainfall, 0.0), 1.0)

                            rainfall *= temperature

                            if quad.biomeTintType:
                                if quad.biomeTintType == blockmodels.BIOME_GRASS:
                                    imageX = <unsigned int>((1.0 - temperature) * (blockModels.grassImageX - 1))
                                    imageY = <unsigned int>((1.0 - rainfall) * (blockModels.grassImageY - 1))
                                    imageOffset = imageX + blockModels.grassImageX * imageY
                                    tintColor = &blockModels.grassImageBits[imageOffset * 4]
                                if quad.biomeTintType == blockmodels.BIOME_FOLIAGE:
                                    imageX = <unsigned int>((1.0 - temperature) * (blockModels.foliageImageX - 1))
                                    imageY = <unsigned int>((1.0 - rainfall) * (blockModels.foliageImageY - 1))
                                    imageOffset = imageX + blockModels.foliageImageX * imageY
                                    tintColor = &blockModels.foliageImageBits[imageOffset * 4]

                                vertexColor = <unsigned char *>xyzuvstc
                                for vertex in range(4):
                                    for channel in range(3):
                                        color = vertexColor[vertexBytes * vertex + vertexBytes - 4 + channel]
                                        # format is ARGB8, but this is with respect to 4-byte words
                                        # when the words are little endian, the byte ordering becomes BGRA
                                        # what i REALLY SHOULD do is get the pixel as an int and bit shift the bytes out.
                                        color *= tintColor[2-channel]
                                        color >>= 8
                                        vertexColor[vertexBytes * vertex + vertexBytes - 4 + channel] = <unsigned char>color


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
                                vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * quadFloats)

                    elif renderType[ID] == 1:
                        if ID == waterFlowID or ID == waterID:
                            fluidTex = waterTex
                        elif ID == lavaFlowID or ID == lavaID:
                            fluidTex = lavaTex
                        else:
                            continue
                        if meta > 8:
                            meta = 8  # "falling" water - always full cube

                        # upID = areaBlocks[y+1, z, x]
                        # if upID == waterID or upID == waterFlowID or upID == lavaID or upID == lavaFlowID:
                        #     quads = blockModels.fluidQuads[8]  # block above has fluid - fill this fluid block
                        # else:
                        quads = blockModels.fluidQuads[meta]

                        bl = areaBlockLight[y, z, x]  # xxx block.useNeighborLighting
                        sl = areaSkyLight[y, z, x]
                        for i in range(6):
                            quad = quads.quads[i]
                            nx = x + quad.quadface[1]
                            ny = y + quad.quadface[2]
                            nz = z + quad.quadface[3]
                            nID = areaBlocks[ny, nz, nx]
                            if opaqueCube[nID]:
                                continue
                            if nID == waterID or nID == waterFlowID or nID == lavaID or nID == lavaFlowID:
                                nMeta = areaData[ny, nz, nx]
                                if nMeta > 7 or 7 - (nMeta & 0x7) >= 7 - (meta & 0x7):
                                    continue  # cull face as the neighboring block is fuller

                            xyzuvstc = vertexBuffer + buffer_ptr * quadFloats
                            memcpy(xyzuvstc, quad.xyzuvstc, sizeof(float) * quadFloats)

                            xyzuvstc[0] += rx
                            xyzuvstc[1] += ry
                            xyzuvstc[2] += rz
                            xyzuvstc[3] += fluidTex[0]
                            xyzuvstc[4] += fluidTex[1]
                            xyzuvstc[5] += bl
                            xyzuvstc[6] += sl


                            xyzuvstc[8] += rx
                            xyzuvstc[9] += ry
                            xyzuvstc[10] += rz
                            xyzuvstc[11] += fluidTex[0]
                            xyzuvstc[12] += fluidTex[1]
                            xyzuvstc[13] += bl
                            xyzuvstc[14] += sl


                            xyzuvstc[16] += rx
                            xyzuvstc[17] += ry
                            xyzuvstc[18] += rz
                            xyzuvstc[19] += fluidTex[0]
                            xyzuvstc[20] += fluidTex[1]
                            xyzuvstc[21] += bl
                            xyzuvstc[22] += sl


                            xyzuvstc[24] += rx
                            xyzuvstc[25] += ry
                            xyzuvstc[26] += rz
                            xyzuvstc[27] += fluidTex[0]
                            xyzuvstc[28] += fluidTex[1]
                            xyzuvstc[29] += bl
                            xyzuvstc[30] += sl

                            buffer_ptr += 1

                            if buffer_ptr >= buffer_size:
                                buffer_size *= 2
                                vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * quadFloats)

        if buffer_ptr:  # now buffer size
            vertexArray = QuadVertexArrayBuffer(buffer_ptr)
            vabuffer = vertexArray.buffer
            memcpy(vabuffer.data, vertexBuffer, buffer_ptr * sizeof(float) * quadFloats)
            self.sceneNode = scenegraph.VertexNode(vertexArray)
        free(vertexBuffer)
