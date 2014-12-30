"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import registerBlockRenderer, directionOffsets
from mcedit2.rendering.blockmeshes.blockmesh import BlockMeshBase
from mcedit2.rendering.slices import _XYZST
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)

directionalBrightness = [
    .8, .8, 1., .5, .6, .6,
]
@registerBlockRenderer("Standard")
class StandardBlockMesh(BlockMeshBase):
    renderstate = renderstates.RenderstateAlphaTestNode
    extraTextures = ["grass_side_overlay",
                     ]

    def makeGenericVertices(self):
        vertexArrays = []
        renderTypeMask = self.getRenderTypeMask()
        yield
        updateTask = self.sectionUpdate.chunkUpdate.updateTask

        for (direction, exposedFaceMask) in enumerate(self.sectionUpdate.exposedBlockMasks):
            blockIndices = renderTypeMask & exposedFaceMask

            theseBlocks = self.sectionUpdate.Blocks[blockIndices]
            bdata = self.sectionUpdate.Data[blockIndices]

            vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
            if not len(vertexBuffer.vertex):
                continue
            blockSizes = self.sectionUpdate.blocktypes.cubeBounds[theseBlocks, bdata]
            applyBlockSizes(vertexBuffer, direction, blockSizes)

            vertexBuffer.applyTexMap(updateTask.lookupTextures(theseBlocks, bdata, direction))

            facingSkyLight = self.sectionUpdate.areaSkyLights[directionOffsets[direction]]
            skyLight = facingSkyLight[blockIndices]

            facingBlockLight = self.sectionUpdate.areaBlockLights[directionOffsets[direction]]
            blockLight = facingBlockLight[blockIndices]

            vertexBuffer.setLights(skyLight, blockLight)

            colors = self.sectionUpdate.chunkUpdate.chunk.blocktypes.renderColor[theseBlocks, bdata]
            vertexArrays.append(vertexBuffer)

            if direction != faces.FaceYIncreasing:
                grass = theseBlocks == self.sectionUpdate.blocktypes.Grass.ID
                colors[grass] = 0xff, 0xff, 0xff
                #if direction != faces.FaceZIncreasing:
                #    overlay = VertexArrayBuffer(0)
                #    overlay.buffer = numpy.array(vertexBuffer.buffer)

            vertexBuffer.rgb[:] = colors[:, None]
            vertexBuffer.rgb[:] *= directionalBrightness[direction]
            #numpy.set_printoptions(threshold=99999)
            #print (vertexBuffer.lightcoord)

            #if self.blocktypes.name in ("Alpha", "Pocket"):
            #    if direction == mceditlib.faces.FaceYIncreasing:
            #        grass = theseBlocks == mceditlib.blocktypes.pc_blocktypes.Grass.ID
            #        vertexBuffer.rgb[grass] *= self.grassColor


            yield



        self.vertexArrays = vertexArrays

    grassColor = grassColorDefault = [0.39, 0.77, 0.23]  # 62C743

    makeVertices = makeGenericVertices


def applyBlockSizes(vertexBuffer, face, sizes):
    xmin = sizes[..., 0]
    ymin = sizes[..., 1]
    zmin = sizes[..., 2]
    xmax = sizes[..., 3]
    ymax = sizes[..., 4]
    zmax = sizes[..., 5]

    buf = vertexBuffer.buffer[_XYZST].swapaxes(0, 2).swapaxes(0, 1)

    if face == faces.FaceXIncreasing:
        buf[:] += [(xmax, ymin, zmax, zmin, ymin),
                   (xmax, ymin, zmin, zmax, ymin),
                   (xmax, ymax, zmin, zmax, ymax),
                   (xmax, ymax, zmax, zmin, ymax)]

    if face == faces.FaceXDecreasing:
        buf[:] += [(xmin, ymin, zmin, zmin, ymin),
                   (xmin, ymin, zmax, zmax, ymin),
                   (xmin, ymax, zmax, zmax, ymax),
                   (xmin, ymax, zmin, zmin, ymax)]

    if face == faces.FaceYIncreasing:
        tmax = 1 - zmax
        tmin = 1 - zmin
        buf[:] += [(xmin, ymax, zmin, xmin, tmax), # ne
                   (xmin, ymax, zmax, xmin, tmin), # nw
                   (xmax, ymax, zmax, xmax, tmin), # sw
                   (xmax, ymax, zmin, xmax, tmax)]  # se

    if face == faces.FaceYDecreasing:
        tmax = 1 - zmax
        tmin = 1 - zmin
        buf[:] += [(xmin, ymin, zmin, xmin, tmax),
                   (xmax, ymin, zmin, xmax, tmax),
                   (xmax, ymin, zmax, xmax, tmin),
                   (xmin, ymin, zmax, xmin, tmin)]

    if face == faces.FaceZIncreasing:
        buf[:] += [(xmin, ymin, zmax, xmin, ymin),
                   (xmax, ymin, zmax, xmax, ymin),
                   (xmax, ymax, zmax, xmax, ymax),
                   (xmin, ymax, zmax, xmin, ymax)]

    if face == faces.FaceZDecreasing:
        buf[:] += [(xmax, ymin, zmin, xmin, ymin),
                   (xmin, ymin, zmin, xmax, ymin),
                   (xmin, ymax, zmin, xmax, ymax),
                   (xmax, ymax, zmin, xmin, ymax)]
