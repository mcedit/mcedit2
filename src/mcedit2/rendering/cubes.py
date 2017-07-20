"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
import numpy
from mcedit2.util.glutils import gl
from mceditlib import faces

log = logging.getLogger(__name__)

def drawBox(box, cubeType=GL.GL_QUADS, texture=None, textureVertices=None, selectionBox=False):
    """ pass a different cubeType e.g. GL_LINE_STRIP for wireframes """
    x, y, z, = box.origin
    x2, y2, z2 = box.maximum
    dx, dy, dz = x2 - x, y2 - y, z2 - z
    cubeVertices = numpy.array(
        (
            x, y, z,
            x, y2, z,
            x2, y2, z,
            x2, y, z,

            x2, y, z2,
            x2, y2, z2,
            x, y2, z2,
            x, y, z2,

            x2, y, z2,
            x, y, z2,
            x, y, z,
            x2, y, z,

            x2, y2, z,
            x, y2, z,
            x, y2, z2,
            x2, y2, z2,

            x, y2, z2,
            x, y2, z,
            x, y, z,
            x, y, z2,

            x2, y, z2,
            x2, y, z,
            x2, y2, z,
            x2, y2, z2,
        ), dtype='f4')
    if textureVertices is None and texture is not None:
        textureVertices = numpy.array(
            (
                0, -dy * 16,
                0, 0,
                dx * 16, 0,
                dx * 16, -dy * 16,

                dx * 16, -dy * 16,
                dx * 16, 0,
                0, 0,
                0, -dy * 16,

                dx * 16, -dz * 16,
                0, -dz * 16,
                0, 0,
                dx * 16, 0,

                dx * 16, 0,
                0, 0,
                0, -dz * 16,
                dx * 16, -dz * 16,

                dz * 16, 0,
                0, 0,
                0, -dy * 16,
                dz * 16, -dy * 16,

                dz * 16, -dy * 16,
                0, -dy * 16,
                0, 0,
                dz * 16, 0,

            ), dtype='f4')

        textureVertices.shape = (6, 4, 2)

        if selectionBox:
            textureVertices[0:2] += (16 * (x & 15), 16 * (y2 & 15))
            textureVertices[2:4] += (16 * (x & 15), -16 * (z & 15))
            textureVertices[4:6] += (16 * (z & 15), 16 * (y2 & 15))
            textureVertices[:] += 0.5

    with gl.glPushAttrib(GL.GL_TEXTURE_BIT):
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, cubeVertices)
        if texture is not None:
            GL.glEnable(GL.GL_TEXTURE_2D)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)

            texture.bind()
            GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, textureVertices),

        with gl.glPushAttrib(GL.GL_POLYGON_BIT):
            GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
            GL.glEnable(GL.GL_POLYGON_OFFSET_LINE)

            GL.glDrawArrays(cubeType, 0, 24)
        if texture is not None:
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)



def drawFace(box, face, elementType=GL.GL_QUADS):
    x, y, z, = box.origin
    x2, y2, z2 = box.maximum

    if face == faces.FaceXDecreasing:
        faceVertices = numpy.array(
            (x, y2, z2,
             x, y2, z,
             x, y, z,
             x, y, z2,
            ), dtype='f4')

    elif face == faces.FaceXIncreasing:
        faceVertices = numpy.array(
            (x2, y, z2,
             x2, y, z,
             x2, y2, z,
             x2, y2, z2,
            ), dtype='f4')

    elif face == faces.FaceYDecreasing:
        faceVertices = numpy.array(
            (x2, y, z2,
             x, y, z2,
             x, y, z,
             x2, y, z,
            ), dtype='f4')

    elif face == faces.FaceYIncreasing:
        faceVertices = numpy.array(
            (x2, y2, z,
             x, y2, z,
             x, y2, z2,
             x2, y2, z2,
            ), dtype='f4')

    elif face == faces.FaceZDecreasing:
        faceVertices = numpy.array(
            (x, y, z,
             x, y2, z,
             x2, y2, z,
             x2, y, z,
            ), dtype='f4')

    elif face == faces.FaceZIncreasing:
        faceVertices = numpy.array(
            (x2, y, z2,
             x2, y2, z2,
             x, y2, z2,
             x, y, z2,
            ), dtype='f4')
    else:
        raise ValueError("Unknown face %s" % face)

    faceVertices.shape = (4, 3)
    dim = face >> 1
    dims = [0, 1, 2]
    dims.remove(dim)

    texVertices = numpy.array(
        faceVertices[:, dims],
        dtype='f4'
    ).flatten()
    faceVertices.shape = (12,)

    texVertices *= 16
    GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)

    GL.glVertexPointer(3, GL.GL_FLOAT, 0, faceVertices)
    GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, texVertices)

    with gl.glPushAttrib(GL.GL_POLYGON_BIT):
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glEnable(GL.GL_POLYGON_OFFSET_LINE)

        if elementType is GL.GL_LINE_STRIP:
            indexes = numpy.array((0, 1, 2, 3, 0), dtype='uint32')
            GL.glDrawElements(elementType, 5, GL.GL_UNSIGNED_INT, indexes)
        else:
            GL.glDrawArrays(elementType, 0, 4)

    GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)


def drawConstructionCube(box, color, texture=None):
    #if texture == None:
    #    texture = self.sixteenBlockTex
    with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT):
        GL.glEnable(GL.GL_BLEND)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthMask(False)

        # edges within terrain
        GL.glDepthFunc(GL.GL_GREATER)
        GL.glColor(color[0], color[1], color[2], max(color[3], 0.35))
        GL.glLineWidth(1.0)
        drawBox(box, cubeType=GL.GL_LINE_STRIP)

        # edges on or outside terrain
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glColor(color[0], color[1], color[2], max(color[3] * 2, 0.75))
        GL.glLineWidth(2.0)
        drawBox(box, cubeType=GL.GL_LINE_STRIP)

        # faces
        GL.glDepthFunc(GL.GL_LESS)
        GL.glColor(color[0], color[1], color[2], color[3])
        GL.glDepthFunc(GL.GL_LEQUAL)
        drawBox(box, texture=texture, selectionBox=True)



def drawTerrainCuttingWire(box,
                           c0=(0.75, 0.75, 0.75, 0.4),
                           c1=(1.0, 1.0, 1.0, 1.0)):

    GL.glEnable(GL.GL_DEPTH_TEST)

    # Above ground parts
    GL.glDepthFunc(GL.GL_LEQUAL)
    GL.glColor(*c1)
    GL.glLineWidth(2.0)
    drawBox(box, cubeType=GL.GL_LINE_STRIP)

    # Below ground parts
    GL.glDepthFunc(GL.GL_GREATER)
    GL.glColor(*c0)
    GL.glLineWidth(1.0)
    drawBox(box, cubeType=GL.GL_LINE_STRIP)

    GL.glDepthFunc(GL.GL_LEQUAL)
    GL.glDisable(GL.GL_DEPTH_TEST)
