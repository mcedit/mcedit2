"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import defaultdict
import logging

import numpy
from OpenGL import GL

from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.util.glutils import Texture, gl
from mcedit2.rendering.depths import DepthOffsets

log = logging.getLogger(__name__)

log.info("Making checkerboard texture...")
color0 = (0xff, 0xff, 0xff, 0x22)
color1 = (0xff, 0xff, 0xff, 0x44)

floorTexImage = numpy.array([color0, color1, color1, color0], dtype='uint8')

class LoadableChunksRenderNode(rendernode.RenderNode):
    floorTexture = None

    def compile(self):
        if self.floorTexture is None:
            self.floorTexture = Texture(image=floorTexImage, width=2, height=2,
                                        minFilter=GL.GL_NEAREST,
                                        magFilter=GL.GL_NEAREST,
                                        )
            self.floorTexture.load()
        super(LoadableChunksRenderNode, self).compile()

    def drawSelf(self):
        with gl.glPushAttrib(GL.GL_FOG_BIT | GL.GL_ENABLE_BIT):
            GL.glDisable(GL.GL_FOG)

            GL.glEnable(GL.GL_BLEND)
            GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
            GL.glPolygonOffset(DepthOffsets.ChunkMarkers, DepthOffsets.ChunkMarkers)
            GL.glEnable(GL.GL_DEPTH_TEST)

            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
            GL.glEnable(GL.GL_TEXTURE_2D)
            GL.glColor(1.0, 1.0, 1.0, 1.0)

            self.floorTexture.bind()

            for vertexArray in self.sceneNode.createVertexArrays():
                GL.glVertexPointer(3, GL.GL_FLOAT, 0, vertexArray.ravel())
                # chunkPositions *= 8
                GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, (vertexArray[..., (0, 2)] / 32).ravel())
                GL.glDrawArrays(GL.GL_QUADS, 0, len(vertexArray) * 4)
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)


class LoadableChunksNode(scenenode.Node):
    skipLargeLevels = False
    RenderNodeClass = LoadableChunksRenderNode

    def __init__(self, dimension):
        super(LoadableChunksNode, self).__init__()
        self.dimension = dimension

        # if self.skipLargeLevels: # and hasattr(self.dimension.worldEditor, 'worldFolder'):
        #     try:
        #         p = self.dimension.worldEditor.adapter.selectedRevision.getFolderPath('region')
        #         if len(os.listdir(p)) > 50:  # 50 * 1024 chunks
        #             return
        #
        #     except AttributeError:
        #         log.exception("Don't know how to count region files in %s", self.dimension)
        #         raise

    def createVertexArrays(self):

        if self.dimension.chunkCount:
            chunkSet = set(self.dimension.chunkPositions())
            sizedChunks = chunkMarkers(chunkSet)

            def arrays():
                for size, chunks in sizedChunks.iteritems():
                    if not len(chunks):
                        continue
                    chunks = numpy.array(chunks, dtype='float32')

                    chunkPositions = numpy.zeros(shape=(chunks.shape[0], 4, 3), dtype='float32')
                    chunkPositions[:, :, (0, 2)] = numpy.array(((0, 0), (0, 1), (1, 1), (1, 0)), dtype='float32')
                    chunkPositions[:, :, (0, 2)] *= size
                    chunkPositions[:, :, (0, 2)] += chunks[:, numpy.newaxis, :]
                    chunkPositions *= 16
                    yield chunkPositions

            return list(arrays())

def chunkMarkers(chunkSet):
    """ Returns a mapping { size: [position, ...] } for different powers of 2
    as size.
    """

    sizedChunks = defaultdict(list)
    size = 1

    def all4(cx, cz):
        cx &= ~size
        cz &= ~size
        return [(cx, cz), (cx + size, cz), (cx + size, cz + size), (cx, cz + size)]

    # lastsize = 6
    size = 1
    while True:
        nextsize = size << 1
        chunkSet = set(chunkSet)
        while len(chunkSet):
            cx, cz = chunkSet.pop()
            chunkSet.add((cx, cz))
            o = all4(cx, cz)
            others = set(o).intersection(chunkSet)
            if len(others) == 4:
                sizedChunks[nextsize].append(o[0])
                for c in others:
                    chunkSet.discard(c)
            else:
                for c in others:
                    sizedChunks[size].append(c)
                    chunkSet.discard(c)

        if len(sizedChunks[nextsize]):
            chunkSet = set(sizedChunks[nextsize])
            sizedChunks[nextsize] = []
            size <<= 1
        else:
            break
    return sizedChunks
