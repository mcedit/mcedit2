"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import BlockMeshBase, registerBlockRenderer
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)

@registerBlockRenderer("Torch")
class TorchBlockMesh(BlockMeshBase):
    blocktypes = [50, 75, 76]
    renderstate = renderstates.RenderstateAlphaTestNode
    torchOffsetsStraight = [
        [# FaceXIncreasing
         (-7 / 16., 0, 0),
         (-7 / 16., 0, 0),
         (-7 / 16., 0, 0),
         (-7 / 16., 0, 0),
        ],
        [# FaceXDecreasing
         (7 / 16., 0, 0),
         (7 / 16., 0, 0),
         (7 / 16., 0, 0),
         (7 / 16., 0, 0),
        ],
        [# FaceYIncreasing
         (7 / 16., -6 / 16., 7 / 16.),
         (7 / 16., -6 / 16., -7 / 16.),
         (-7 / 16., -6 / 16., -7 / 16.),
         (-7 / 16., -6 / 16., 7 / 16.),
        ],
        [# FaceYDecreasing
         (7 / 16., 0., 7 / 16.),
         (-7 / 16., 0., 7 / 16.),
         (-7 / 16., 0., -7 / 16.),
         (7 / 16., 0., -7 / 16.),
        ],

        [# FaceZIncreasing
         (0, 0, -7 / 16.),
         (0, 0, -7 / 16.),
         (0, 0, -7 / 16.),
         (0, 0, -7 / 16.)
        ],
        [# FaceZDecreasing
         (0, 0, 7 / 16.),
         (0, 0, 7 / 16.),
         (0, 0, 7 / 16.),
         (0, 0, 7 / 16.)
        ],

    ]

    torchOffsetsSouth = [
        [# FaceXIncreasing
         (-7 / 16., 3 / 16., 0),
         (-7 / 16., 3 / 16., 0),
         (-7 / 16., 3 / 16., 0),
         (-7 / 16., 3 / 16., 0),
        ],
        [# FaceXDecreasing
         (7 / 16., 3 / 16., 0),
         (7 / 16., 3 / 16., 0),
         (7 / 16., 3 / 16., 0),
         (7 / 16., 3 / 16., 0),
        ],
        [# FaceYIncreasing
         (7 / 16., -3 / 16., 7 / 16.),
         (7 / 16., -3 / 16., -7 / 16.),
         (-7 / 16., -3 / 16., -7 / 16.),
         (-7 / 16., -3 / 16., 7 / 16.),
        ],
        [# FaceYDecreasing
         (7 / 16., 3 / 16., 7 / 16.),
         (-7 / 16., 3 / 16., 7 / 16.),
         (-7 / 16., 3 / 16., -7 / 16.),
         (7 / 16., 3 / 16., -7 / 16.),
        ],

        [# FaceZIncreasing
         (0, 3 / 16., -7 / 16.),
         (0, 3 / 16., -7 / 16.),
         (0, 3 / 16., -7 / 16.),
         (0, 3 / 16., -7 / 16.)
        ],
        [# FaceZDecreasing
         (0, 3 / 16., 7 / 16.),
         (0, 3 / 16., 7 / 16.),
         (0, 3 / 16., 7 / 16.),
         (0, 3 / 16., 7 / 16.),
        ],

    ]
    torchOffsetsNorth = torchOffsetsWest = torchOffsetsEast = torchOffsetsSouth

    torchOffsets = [
                       torchOffsetsStraight,
                       torchOffsetsSouth,
                       torchOffsetsNorth,
                       torchOffsetsWest,
                       torchOffsetsEast,
                       torchOffsetsStraight,
                   ] + [torchOffsetsStraight] * 10

    torchOffsets = numpy.array(torchOffsets, dtype='float32')

    torchOffsets[1][..., 3, :, 0] -= 0.5

    torchOffsets[1][..., 0:2, 0:2, 0] -= 0.5
    torchOffsets[1][..., 4:6, 0:2, 0] -= 0.5
    torchOffsets[1][..., 0:2, 2:4, 0] -= 0.1
    torchOffsets[1][..., 4:6, 2:4, 0] -= 0.1

    torchOffsets[1][..., 2, :, 0] -= 0.25

    torchOffsets[2][..., 3, :, 0] += 0.5
    torchOffsets[2][..., 0:2, 0:2, 0] += 0.5
    torchOffsets[2][..., 4:6, 0:2, 0] += 0.5
    torchOffsets[2][..., 0:2, 2:4, 0] += 0.1
    torchOffsets[2][..., 4:6, 2:4, 0] += 0.1
    torchOffsets[2][..., 2, :, 0] += 0.25

    torchOffsets[3][..., 3, :, 2] -= 0.5
    torchOffsets[3][..., 0:2, 0:2, 2] -= 0.5
    torchOffsets[3][..., 4:6, 0:2, 2] -= 0.5
    torchOffsets[3][..., 0:2, 2:4, 2] -= 0.1
    torchOffsets[3][..., 4:6, 2:4, 2] -= 0.1
    torchOffsets[3][..., 2, :, 2] -= 0.25

    torchOffsets[4][..., 3, :, 2] += 0.5
    torchOffsets[4][..., 0:2, 0:2, 2] += 0.5
    torchOffsets[4][..., 4:6, 0:2, 2] += 0.5
    torchOffsets[4][..., 0:2, 2:4, 2] += 0.1
    torchOffsets[4][..., 4:6, 2:4, 2] += 0.1
    torchOffsets[4][..., 2, :, 2] += 0.25

    upCoords = ((7, 6), (7, 8), (9, 8), (9, 6))
    downCoords = ((7, 14), (7, 16), (9, 16), (9, 14))

    def makeTorchVertices(self):

        blockIndices = self.getRenderTypeMask()
        data = self.sectionUpdate.Data[blockIndices]
        torchOffsets = self.torchOffsets[data]
        texes = self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], data, 0)  # xxx assuming same tex on all sides!!
        yield

        arrays = []
        blockLight = self.sectionUpdate.chunkSection.BlockLight[blockIndices]
        skyLight = self.sectionUpdate.chunkSection.SkyLight[blockIndices]

        for direction in range(6):
            vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
            if not len(vertexBuffer):
                return

            vertexBuffer.rgba[:] = 0xff
            vertexBuffer.vertex[:] += torchOffsets[:, direction]
            vertexBuffer.applyTexMap(texes)
            if direction == faces.FaceYIncreasing:
                vertexBuffer.texcoord[:] += self.upCoords
            if direction == faces.FaceYDecreasing:
                vertexBuffer.texcoord[:] += self.downCoords

            vertexBuffer.setLights(skyLight, blockLight)
            arrays.append(vertexBuffer)
            yield

        self.vertexArrays = arrays

    makeVertices = makeTorchVertices
