"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import itertools
import logging
import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)


class BlockModelMesh(object):
    renderstate = renderstates.RenderstateAlphaTestNode
    def __init__(self, sectionUpdate):
        """

        :param sectionUpdate:
        :type sectionUpdate: SectionUpdate
        :return:
        :rtype:
        """
        self.sectionUpdate = sectionUpdate
        self.vertexArrays = []

    def createVertexArrays(self):
        chunk = self.sectionUpdate.chunkUpdate.chunk
        cx, cz = chunk.chunkPosition
        cy = self.sectionUpdate.cy
        section = chunk.getSection(cy)
        if section is None:
            return

        blockModels = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas.blockModels
        blocktypes = self.sectionUpdate.blocktypes
        areaBlocks = self.sectionUpdate.areaBlocks
        faceQuadVerts = []
        
        cdef unsigned short y, z, x, ID, meta
        cdef short dx, dy, dz,
        cdef unsigned short nx, ny, nz, nID

        for y in range(1, 17):
            for z in range(1, 17):
                for x in range(1, 17):
                    ID = areaBlocks[y, z, x]
                    if ID == 0:
                        continue
                    meta = section.Data[y-1, z-1, x-1]

                    block = blocktypes[ID, meta]
                    if block.renderType != 3:  # only model blocks for now
                        continue
                    nameAndState = block.internalName + block.blockState
                    quads = blockModels.cookedModels[nameAndState]

                    for face, xyzuvc, cullface in quads:
                        if cullface is not None:
                            dx, dy, dz = cullface.vector
                            nx = x + dx
                            ny = y + dy
                            nz = z + dz
                            nID = areaBlocks[ny, nz, nx]
                            if nID != 0:
                                nBlock = blocktypes[nID]
                                if nBlock.opaqueCube:
                                    continue

                        verts = numpy.array(xyzuvc)
                        verts.shape = 1, 4, 6
                        verts[..., :3] += (x - 1, y - 1 + (cy << 4), z - 1)
                        faceQuadVerts.append(verts)
                        # log.info("Block %s:\nVertices: %s", (x-1, y-1, z-1), verts)

        # raise SystemExit
        if len(faceQuadVerts):
            vertexArray = VertexArrayBuffer(len(faceQuadVerts), lights=False)
            vertexArray.buffer[..., :6] = numpy.vstack(faceQuadVerts)
            self.vertexArrays = [vertexArray]
