from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy
from mcedit2.rendering.blockmeshes.blockmesh import BlockMeshBase, directionOffsets

from mcedit2.util.scanmodules import ScanModules

log = logging.getLogger(__name__)

internal_rendertypes = """
Internal rendertypes used by Minecraft:

0	 StandardBlock
1	 CrossedSquares
2	 Torch
3	 Fire
4	 Fluids
5	 RedstoneWire
6	 Crops
7	 Door
8	 Ladder
9	 MinecartTrack
10	 Stairs
11	 Fence
12	 Lever
13	 Cactus
14	 Bed
15	 Repeater
16	 PistonBase
17	 PistonExtension
18	 Pane
19	 Stem
20	 Vine
21	 FenceGate
23	 LilyPad
24	 Cauldron
25	 BrewingStand
26	 EndPortalFrame
27	 DragonEgg
28	 Cocoa
29	 TripWireSource
30	 TripWire
31	 Log
32	 Wall
33	 Flowerpot
34	 Beacon
35	 Anvil
36	 RedstoneLogic
37	 Comparator
38	 Hopper
39	 Quartz

"""


def makeVertexTemplates(xmin=0, ymin=0, zmin=0, xmax=1, ymax=1, zmax=1):
    return numpy.array([

        # FaceXIncreasing:
        [(xmax, ymin, zmax, zmin, ymin),
         (xmax, ymin, zmin, zmax, ymin),
         (xmax, ymax, zmin, zmax, ymax),
         (xmax, ymax, zmax, zmin, ymax)],

        # FaceXDecreasing:
        [(xmin, ymin, zmin, zmin, ymin),
         (xmin, ymin, zmax, zmax, ymin),
         (xmin, ymax, zmax, zmax, ymax),
         (xmin, ymax, zmin, zmin, ymax)],

        # FaceYIncreasing:
        [(xmin, ymax, zmin, xmin, 1 - zmax), # ne
         (xmin, ymax, zmax, xmin, 1 - zmin), # nw
         (xmax, ymax, zmax, xmax, 1 - zmin), # sw
         (xmax, ymax, zmin, xmax, 1 - zmax)], # se

        # FaceYDecreasing:
        [(xmin, ymin, zmin, xmin, 1 - zmax),
         (xmax, ymin, zmin, xmax, 1 - zmax),
         (xmax, ymin, zmax, xmax, 1 - zmin),
         (xmin, ymin, zmax, xmin, 1 - zmin)],

        # FaceZIncreasing:
        [(xmin, ymin, zmax, xmin, ymin),
         (xmax, ymin, zmax, xmax, ymin),
         (xmax, ymax, zmax, xmax, ymax),
         (xmin, ymax, zmax, xmin, ymax)],

        # FaceZDecreasing:
        [(xmax, ymin, zmin, xmin, ymin),
         (xmin, ymin, zmin, xmax, ymin),
         (xmin, ymax, zmin, xmax, ymax),
         (xmax, ymax, zmin, xmin, ymax)],
    ])


standardCubeTemplates = makeVertexTemplates()

from mceditlib.blocktypes import rendertypes

renderTypesByName = {v: k for k, v in rendertypes.renderTypes.iteritems()}
_registeredBlockRenderers = {}


def registerBlockRenderer(renderTypeName):
    def _decorator(cls):
        cls.renderType = renderTypesByName[renderTypeName]
        _registeredBlockRenderers[cls.renderType] = cls

        return cls

    return _decorator


def getRendererClasses():
    global _scanned_modules
    if _scanned_modules is None:
        _scanned_modules = list(ScanMeshModules())

        registeredNames = set(rendertypes.renderTypes[ID] for ID in _registeredBlockRenderers)
        unregisteredNames = set(renderTypesByName.keys()) - registeredNames
        log.warn("Unregistered renderers: \n  %s", ",  ".join(unregisteredNames))

    return dict(_registeredBlockRenderers)


_scanned_modules = None


def getExtraTextureNames():
    for cls in getRendererClasses().itervalues():
        for name in cls.extraTextures:
            yield name


def ScanMeshModules():
    return ScanModules(__name__, __file__)


#
#class SnowBlockMesh(BlockMeshBase):
#    snowID = 78
#
#    blocktypes = [snowID]
#
#    def makeSnowVertices(self, exposedBlockMasks, blocks, blockRenderTypes, blockData, areaBlockLights, areaSkyLights,
#                         lookupTextures):
#        snowIndices = self.getRenderTypeMask(blockRenderTypes)
#        arrays = []
#        yield
#        for direction, exposedFaceMask in enumerate(exposedBlockMasks):
#        # def makeFaceVertices(self, direction, blockIndices, exposedFaceMask, blocks, blockData, blockLight, facingBlockLight, skyLight, facingSkyLight, lookupTextures):
#        # return []
#
#            if direction != mceditlib.faces.FaceYIncreasing:
#                blockIndices = snowIndices & exposedFaceMask
#            else:
#                blockIndices = snowIndices
#
#            facingBlockLight = areaBlockLights[directionOffsets[direction]]
#            facingSkyLight = areaSkyLights[directionOffsets[direction]]
#
#            vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
#            if not len(vertexBuffer):
#                continue
#
#            vertexBuffer.texcoord[:] += lookupTextures([self.snowID], 0, 0)[:, numpy.newaxis, 0:2]
#
#            vertexBuffer.setLights(facingSkyLight[blockIndices], facingBlockLight[blockIndices])
#
#            if direction == mceditlib.faces.FaceYIncreasing:
#                vertexBuffer.vertex[..., 1] -= 0.875
#
#            if direction != mceditlib.faces.FaceYIncreasing and direction != mceditlib.faces.FaceYDecreasing:
#                vertexBuffer.vertex[..., 2:4, 1] -= 0.875
#                vertexBuffer.texcoord[..., 2:4, 1] += 14
#
#            arrays.append(vertexBuffer)
#            yield
#        self.vertexArrays = arrays
#
#    makeVertices = makeSnowVertices

# button, floor plate, door -> 1-cube features xxx most of these are bounds now

#
#class SlabBlockMesh(BlockMeshBase):
#    blocktypes = [44, 126]
#
#    def slabFaceVertices(self, direction, blockIndices, exposedFaceMask, blocks, blockData, blockLight,
#                         facingBlockLight, skyLight, facingSkyLight, lookupTextures):
#        if direction != mceditlib.faces.FaceYIncreasing:
#            blockIndices = blockIndices & exposedFaceMask
#
#        bdata = blockData[blockIndices]
#        top = (bdata >> 3).astype(bool)
#        bdata &= 7
#
#        vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
#        if not len(vertexBuffer):
#            return vertexBuffer
#
#        vertexBuffer.texcoord[:] += lookupTextures(blocks[blockIndices], bdata, direction)[:, numpy.newaxis, 0:2]
#
#        vertexBuffer.setLights(facingSkyLight[blockIndices], facingBlockLight[blockIndices])
#
#        if direction == mceditlib.faces.FaceYIncreasing:
#            vertexBuffer.vertex[..., 1] -= 0.5
#
#        if direction != mceditlib.faces.FaceYIncreasing and direction != mceditlib.faces.FaceYDecreasing:
#            vertexBuffer.vertex[..., 2:4, 1] -= 0.5
#            vertexBuffer.texcoord[..., 2:4, 1] += 8
#
#        vertexBuffer.vertex[..., 1][top] += 0.5
#
#        return vertexBuffer
#
#    makeFaceVertices = slabFaceVertices

#
#class IceBlockMesh(BlockMeshBase):
#    iceID = 79
#    blocktypes = [iceID]
#    renderstate = renderstates.renderstateIce
#
#    def iceFaceVertices(self, direction, blockIndices, exposedFaceMask, blocks, blockData, blockLight,
#                        facingBlockLight, skyLight, facingSkyLight, lookupTextures):
#        blockIndices = blockIndices & exposedFaceMask
#        vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
#        vertexBuffer.texcoord[:] += lookupTextures(self.iceID, 0, 0)[numpy.newaxis, numpy.newaxis]
#        vertexBuffer.setLights(facingSkyLight[blockIndices], facingBlockLight[blockIndices])
#        return vertexBuffer
#
#    makeFaceVertices = iceFaceVertices


