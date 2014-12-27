"""View frustum modeling as series of clipping planes

Based on code from:
    http://www.markmorley.com/opengl/frustumculling.html
"""

import logging
import numpy
from OpenGL import GL
context_log = logging.getLogger()


def viewingMatrix(projection=None, model=None):
    """Calculate the total viewing matrix from given data

    projection -- the projection matrix, if not provided
        than the result of glGetDoublev( GL_PROJECTION_MATRIX)
        will be used.
    model -- the model-view matrix, if not provided
        than the result of glGetDoublev( GL_MODELVIEW_MATRIX )
        will be used.

    Note:
        Unless there is a valid projection and model-view
        matrix, the function will raise a RuntimeError
    """
    if projection is None:
        projection = GL.glGetDoublev(GL.GL_PROJECTION_MATRIX)
    if model is None:
        model = GL.glGetDoublev(GL.GL_MODELVIEW_MATRIX)
    # hmm, this will likely fail on 64-bit platforms :(
    if projection is None or model is None:
        context_log.warn(
            """A NULL matrix was returned from glGetDoublev: proj=%s modelView=%s""",
            projection, model,
        )
        if projection:
            return projection
        if model:
            return model
        else:
            return numpy.identity(4, 'd')
    if numpy.allclose(projection, -1.79769313e+308):
        context_log.warn(
            """Attempt to retrieve projection matrix when uninitialised %s, model=%s""",
            projection, model,
        )
        return model
    if numpy.allclose(model, -1.79769313e+308):
        context_log.warn(
            """Attempt to retrieve model-view matrix when uninitialised %s, projection=%s""",
            model, projection,
        )
        return projection
    return numpy.dot(model, projection)


class Frustum (object):
    """Holder for frustum specification for intersection tests

    Note:
        the Frustum can include an arbitrary number of
        clipping planes, though the most common usage
        is to define 6 clipping planes from the OpenGL
        model-view matrices.
    """
    def visible(self, points, radius):
        """Determine whether this sphere is visible in frustum

        frustum -- Frustum object holding the clipping planes
            for the view
        matrix -- a matrix which transforms the local
            coordinates to the (world-space) coordinate
            system in which the frustum is defined.

        This version of the method uses a pure-python loop
        to do the actual culling once the points are
        multiplied by the matrix. (i.e. it does not use the
        frustcullaccel C extension module)
        """
        if not len(points):
            return []

        distances = numpy.sum(self.planes[numpy.newaxis, :, :] * points[:, numpy.newaxis, :], -1)
        return ~numpy.any(distances < -radius, -1)

    def visible1(self, point, radius):
        #return self.visible(array(point[numpy.newaxis, :]), radius)

        distance = numpy.sum(self.planes * point, -1)
        vis = ~numpy.any(distance < -radius, -1)
        #assert vis == self.visible(array(point)[numpy.newaxis, :], radius)

        return vis

    @classmethod
    def fromViewingMatrix(cls, matrix=None, normalize=1):
        """Extract and calculate frustum clipping planes from OpenGL

        The default initializer allows you to create
        Frustum objects with arbitrary clipping planes,
        while this alternate initializer provides
        automatic clipping-plane extraction from the
        model-view matrix.

        matrix -- the combined model-view matrix
        normalize -- whether to normalize the plane equations
            to allow for sphere bounding-volumes and use of
            distance equations for LOD-style operations.
        """
        if matrix is None:
            matrix = viewingMatrix()
        clip = numpy.ravel(matrix)
        frustum = numpy.empty((6, 4), 'd')
        # right
        frustum[0][0] = clip[3] - clip[0]
        frustum[0][1] = clip[7] - clip[4]
        frustum[0][2] = clip[11] - clip[8]
        frustum[0][3] = clip[15] - clip[12]
        # left
        frustum[1][0] = clip[3] + clip[0]
        frustum[1][1] = clip[7] + clip[4]
        frustum[1][2] = clip[11] + clip[8]
        frustum[1][3] = clip[15] + clip[12]
        # bottoming
        frustum[2][0] = clip[3] + clip[1]
        frustum[2][1] = clip[7] + clip[5]
        frustum[2][2] = clip[11] + clip[9]
        frustum[2][3] = clip[15] + clip[13]
        # top
        frustum[3][0] = clip[3] - clip[1]
        frustum[3][1] = clip[7] - clip[5]
        frustum[3][2] = clip[11] - clip[9]
        frustum[3][3] = clip[15] - clip[13]
        # far
        frustum[4][0] = clip[3] - clip[2]
        frustum[4][1] = clip[7] - clip[6]
        frustum[4][2] = clip[11] - clip[10]
        frustum[4][3] = clip[15] - clip[14]
        # near
        frustum[5][0] = clip[3] + clip[2]
        frustum[5][1] = clip[7] + clip[6]
        frustum[5][2] = clip[11] + clip[10]
        frustum[5][3] = (clip[15] + clip[14])
        if normalize:
            frustum = cls.normalize(frustum)
        obj = cls()
        obj.planes = frustum
        obj.matrix = matrix
        return obj

    @classmethod
    def normalize(cls, frustum):
        """Normalize clipping plane equations"""
        magnitude = numpy.sqrt(frustum[:, 0] * frustum[:, 0] + frustum[:, 1] * frustum[:, 1] + frustum[:, 2] * frustum[:, 2])
        # eliminate any planes which have 0-length vectors,
        # those planes can't be used for excluding anything anyway...
        frustum = numpy.compress(magnitude, frustum, 0)
        magnitude = numpy.compress(magnitude, magnitude, 0)
        magnitude = numpy.reshape(magnitude.astype('d'), (len(frustum), 1))
        return frustum / magnitude
