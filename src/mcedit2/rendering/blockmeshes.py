from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.layers import Layer
from mceditlib import faces

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
    renderstate = renderstates.RenderstateAlphaTest
    sceneNode = None

    # def bufferSize(self):
    #     return sum(a.buffer.size for a in self.vertexArrays) * 4


class ChunkMeshBase(MeshBase):
    def __init__(self, chunkUpdate):
        """

        :type chunkUpdate: ChunkUpdate
        """
        self.chunkUpdate = chunkUpdate
