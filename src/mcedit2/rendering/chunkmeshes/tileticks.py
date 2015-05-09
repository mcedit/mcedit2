"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering import scenegraph
from mcedit2.rendering.chunkmeshes.entitymesh import EntityMeshBase
from mcedit2.rendering.layers import Layer

log = logging.getLogger(__name__)


class TileTicksRenderer(EntityMeshBase):
    layer = Layer.TileTicks

    def makeChunkVertices(self, chunk, limitBox):
        if hasattr(chunk, "TileTicks"):
            ticks = chunk.TileTicks
            if len(ticks):
                self.sceneNode = scenegraph.VertexNode(
                    self._computeVertices([[t[i].value for i in "xyz"] for t in ticks],
                                          (0xff, 0xff, 0xff, 0x44),
                                          chunkPosition=chunk.chunkPosition))

        yield
