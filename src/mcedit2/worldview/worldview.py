"""
    worldview.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import deque
import logging
import math
import time
import itertools

from OpenGL import GL
from PySide import QtCore, QtGui
from PySide.QtCore import Qt
from PySide.QtOpenGL import QGLWidget
import numpy

from mcedit2.rendering import worldscene, loadablechunks, sky, compass
from mcedit2.rendering.chunknode import ChunkNode
from mcedit2.rendering.frustum import Frustum
from mcedit2.rendering.geometrycache import GeometryCache
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.rendering import scenegraph, rendergraph
from mcedit2.util import profiler, raycast
from mcedit2.widgets.infopanel import InfoPanel
from mceditlib import faces, exceptions
from mceditlib.geometry import Vector, Ray
from mceditlib.selection import rayIntersectsBox
from mceditlib.exceptions import LevelFormatError, ChunkNotPresent
from mceditlib.util import displayName


def worldMeshVertexSize(worldMesh):
    """

    :type worldMesh: WorldScene
    """

    def bufferSizes():
        for cm in worldMesh.chunkGroupNode.children:
            assert isinstance(cm, ChunkNode)
            for bm in cm.getChunkVertexNodes():
                assert isinstance(bm, scenegraph.VertexNode)
                for va in bm.vertexArrays:
                    assert isinstance(va, VertexArrayBuffer)
                    yield va.buffer.nbytes

    return sum(bufferSizes())

log = logging.getLogger(__name__)

class WorldView(QGLWidget):
    """
    Superclass for the following views:

    IsoWorldView: Display the world using an isometric viewing angle, without perspective.
    Click and drag to pan the viewing area. Use the mouse wheel or a UI control to zoom.

    CameraWorldView: Display the world using a first-person viewing angle with perspective.
    Click and drag to pan the camera. Use WASD or click and drag to move the camera.

    CutawayWorldView: Display a single slice of the world. Click and drag to move sideways.
    Use the mouse wheel or a UI widget to move forward or backward. Use a UI widget to zoom.

    FourUpWorldView: Display up to four other world views at once. Default to three cutaways
    and one isometric view.

    """
    viewportMoved = QtCore.Signal(tuple)
    cursorMoved = QtCore.Signal(QtGui.QMouseEvent)

    mouseBlockPos = Vector(0, 0, 0)
    mouseBlockFace = faces.FaceYIncreasing

    def __init__(self, dimension, textureAtlas, geometryCache=None, sharedGLWidget=None):
        """

        :param dimension:
        :type dimension: WorldEditorDimension
        :param textureAtlas:
        :type textureAtlas: TextureAtlas
        :param geometryCache:
        :type geometryCache: GeometryCache
        :param sharedGLWidget:
        :type sharedGLWidget: QGLWidget
        :return:
        :rtype:
        """
        QGLWidget.__init__(self, shareWidget=sharedGLWidget)
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Expanding, QtGui.QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.ClickFocus)
        self.dimension = dimension
        self.worldScene = None
        self.loadableChunksNode = None

        self.mouseRay = Ray(Vector(0, 1, 0), Vector(0, -1, 0))

        self.setMouseTracking(True)

        self.lastAutoUpdate = time.time()
        self.autoUpdateInterval = 0.5  # frequency of screen redraws in response to loaded chunks

        self.compassNode = self.createCompass()
        self.compassOrthoNode = scenegraph.OrthoNode((1, float(self.height()) / self.width()))
        self.compassOrthoNode.addChild(self.compassNode)

        self.viewActions = []
        self.pressedKeys = set()

        self.textureAtlas = textureAtlas

        if geometryCache is None and sharedGLWidget is not None:
            geometryCache = sharedGLWidget.geometryCache
        if geometryCache is None:
            geometryCache = GeometryCache()
        self.geometryCache = geometryCache

        self.matrixNode = scenegraph.MatrixNode()
        self._updateMatrices()

        self.overlayNode = scenegraph.Node()

        self.sceneGraph = self.createSceneGraph()
        self.renderGraph = rendergraph.createRenderNode(self.sceneGraph)

        self.frameSamples = deque(maxlen=500)
        self.frameSamples.append(time.time())

        self.cursorNode = None

    def destroy(self):
        self.worldScene.discardAllChunks()
        super(WorldView, self).destroy()

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__, displayName(self.dimension.worldEditor.filename))

    def createCompass(self):
        return compass.CompassNode()

    def createWorldScene(self):
        return worldscene.WorldScene(self.dimension, self.textureAtlas, self.geometryCache)

    def createSceneGraph(self):
        sceneGraph = scenegraph.Node()
        self.worldScene = self.createWorldScene()

        clearNode = scenegraph.ClearNode()
        skyNode = sky.SkyNode()
        self.loadableChunksNode = loadablechunks.LoadableChunksNode(self.dimension)

        self.matrixNode.addChild(self.loadableChunksNode)
        self.matrixNode.addChild(self.worldScene)
        self.matrixNode.addChild(self.overlayNode)

        sceneGraph.addChild(clearNode)
        sceneGraph.addChild(skyNode)
        sceneGraph.addChild(self.matrixNode)
        sceneGraph.addChild(self.compassOrthoNode)

        return sceneGraph

    def initializeGL(self, *args, **kwargs):
        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glAlphaFunc(GL.GL_NOTEQUAL, 0)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_DEPTH_TEST)

    def setToolCursor(self, cursorNode):
        if self.cursorNode:
            self.matrixNode.removeChild(self.cursorNode)
        if cursorNode:
            self.cursorNode = cursorNode
            self.matrixNode.addChild(cursorNode)

    def setToolOverlays(self, overlayNodes):
        self.overlayNode.clear()
        for node in overlayNodes:
            self.overlayNode.addChild(node)

    def _updateMatrices(self):
        self.updateMatrices()
        self.updateFrustum()
        #min = self.unprojectPoint(0, 0)[0]
        #max = self.unprojectPoint(self.width(), self.height())[0]
        #self.visibleBox = BoundingBox(min, (0, 0, 0)).union(BoundingBox(max, (0, 0, 0)))

    def updateMatrices(self):
        """
        Subclasses must implement updateMatrices to set the projection and modelview matrices.

        Should set self.matrixNode.projection and self.matrixNode.modelview
        """
        raise NotImplementedError

    def updateFrustum(self):
        matrix = self.matrixNode.projection * self.matrixNode.modelview
        self.frustum = Frustum.fromViewingMatrix(numpy.array(matrix.data()))

    def getViewCorners(self):
        """
        Returns corners:
            bottom left, near
            bottom left, far
            top left, near
            top left, far
            bottom right, near
            bottom right, far
            top right, near
            top right, far

        :return:
        :rtype: list[QVector4D]
        """
        corners = [QtGui.QVector4D(x, y, z, 1.) for x, y, z in itertools.product((-1., 1.), (-1., 1.), (0., 1. ))]
        matrix = self.matrixNode.projection * self.matrixNode.modelview
        matrix, inverted = matrix.inverted()
        worldCorners = [matrix.map(corner) for corner in corners]
        worldCorners = [(corner / corner.w()).toTuple()[:3] for corner in worldCorners]
        return worldCorners

    def getViewBounds(self):
        """
        Get the corners of the viewing area, intersected with the world's bounds.
        xxx raycast to intersect with terrain height too

        :return:
        :rtype:
        """
        corners = self.getViewCorners()
        # Convert the 4 corners into rays extending from the near point, then interpolate each ray at the
        # current dimension's height limits
        pairs = []
        for i in range(0, 8, 2):
            pairs.append(corners[i:i+2])

        rays = [Ray.fromPoints(p1, p2) for p1, p2 in pairs]
        bounds = self.dimension.bounds
        pointPairs = [(r.atHeight(bounds.maxy), r.atHeight(bounds.miny)) for r in rays]

        return sum(pointPairs, ())

    def resizeGL(self, width, height):
        GL.glViewport(0, 0, width, height)

        self._updateMatrices()

    def resizeEvent(self, event):
        center = self.viewCenter()
        self.compassOrthoNode.size = (1, float(self.height()) / self.width())
        super(WorldView, self).resizeEvent(event)
        # log.info("WorldView: resized. moving to %s", center)
        # self.centerOnPoint(center)

    _centerPoint = Vector(0, 0, 0)

    @property
    def centerPoint(self):
        return self._centerPoint

    @centerPoint.setter
    def centerPoint(self, value):
        value = Vector(*value)
        if value != self._centerPoint:
            self._centerPoint = value
            self._updateMatrices()
            log.debug("update(): centerPoint %s %s", self, value)
            self.update()
            self.resetLoadOrder()
            self.viewportMoved.emit(self)

    scaleChanged = QtCore.Signal(float)

    _scale = 1. / 16

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self._scale = value
        self._updateMatrices()
        log.debug("update(): scale %s %s", self, value)
        self.update()
        self.scaleChanged.emit(value)
        self.viewportMoved.emit(self)

    def centerOnPoint(self, pos):
        """Center the view on the given position"""
        # delta = self.viewCenter() - self.centerPoint
        # self.centerPoint = pos - delta
        self.centerPoint = pos

    def viewCenter(self):
        """Return the world position at the center of the view."""
        #return self.unprojectAtHeight(self.width() / 2, self.height() / 2, 64.)
        # ray = self.rayAtPosition(self.width() / 2, self.height() / 2)
        # try:
        #     point, face = raycast.rayCastInBounds(ray, self.dimension, 600)
        # except (raycast.MaxDistanceError, ValueError):
        #     point = ray.atHeight(0)
        # return point or ray.point
        return self.centerPoint

    def _anglesToVector(self, yaw, pitch):
        def nanzero(x):
            if math.isnan(x):
                return 0
            else:
                return x

        dx = -math.sin(math.radians(yaw)) * math.cos(math.radians(pitch))
        dy = -math.sin(math.radians(pitch))
        dz = math.cos(math.radians(yaw)) * math.cos(math.radians(pitch))
        return Vector(*map(nanzero, [dx, dy, dz]))

    dragStart = None

    def keyPressEvent(self, event):
        self.augmentKeyEvent(event)
        self.pressedKeys.add(event.key())
        for action in self.viewActions:
            if action.matchKeyEvent(event):
                log.info("Action %s matched event %s", action, event)
                action.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.augmentKeyEvent(event)
        self.pressedKeys.discard(event.key())
        for action in self.viewActions:
            if action.matchKeyEvent(event):
                action.keyReleaseEvent(event)

    def mousePressEvent(self, event):
        self.augmentMouseEvent(event)
        for action in self.viewActions:
            if action.button & event.button():
                if action.modifiers & event.modifiers() or action.modifiers == event.modifiers():
                    if not action.key or action.key in self.pressedKeys:
                        action.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.cursorMoved.emit(event)
        self.update()
        self.augmentMouseEvent(event)
        for action in self.viewActions:
            if not action.button or action.button == event.buttons() or action.button & event.buttons():
                # Important! mouseMove checks event.buttons(), press and release check event.button()
                if action.modifiers & event.modifiers() or action.modifiers == event.modifiers():
                    if not action.key or action.key in self.pressedKeys:
                        action.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.augmentMouseEvent(event)
        for action in self.viewActions:
            if action.button & event.button():
                if action.modifiers & event.modifiers() or action.modifiers == event.modifiers():
                    if not action.key or action.key in self.pressedKeys:
                        action.mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.augmentMouseEvent(event)
        for action in self.viewActions:
            if action.acceptsMouseWheel and ((action.modifiers & event.modifiers()) or action.modifiers == event.modifiers()):
                if action.key in("WHEEL_UP", "WHEEL_DOWN"):
                    for i in range((abs(event.delta()) + 14) / 15):  # xxx 15 = wheel sensitivity?
                        action.keyPressEvent(event)


    def augmentMouseEvent(self, event):
        x, y = event.x(), event.y()
        return self.augmentEvent(x, y, event)

    def augmentKeyEvent(self, event):
        globalPos = QtGui.QCursor.pos()
        mousePos = self.mapFromGlobal(globalPos)
        x = mousePos.x()
        y = mousePos.y()

        # xxx fake position of mouse event -- need to use mcedit internal event object already
        event.x = lambda: x
        event.y = lambda: y

        return self.augmentEvent(x, y, event)

    def augmentEvent(self, x, y, event):
        ray = self.rayAtPosition(x, y)

        event.ray = ray
        event.view = self

        try:
            result = raycast.rayCastInBounds(ray, self.dimension)
            position, face = result

        except (raycast.MaxDistanceError, ValueError):
            GL.glReadBuffer(GL.GL_BACK)
            pixel = GL.glReadPixels(x, self.height() - y, 1, 1, GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT)
            depth = -1 + 2 * pixel[0, 0]
            p = self.pointsAtPositions((x, y, depth))[0]

            face = faces.FaceYIncreasing
            position = p.intfloor()

        self.mouseBlockPos = event.blockPosition = position
        self.mouseBlockFace = event.blockFace = face
        self.mouseRay = ray

    maxFPS = 30

    @profiler.function
    def glDraw(self, *args, **kwargs):
        frameInterval = 1.0 / self.maxFPS
        if time.time() - self.frameSamples[-1] < frameInterval:
            return
        super(WorldView, self).glDraw(*args, **kwargs)

    def paintGL(self):
        with profiler.context("paintGL: %s" % self):
            self.frameSamples.append(time.time())

            with profiler.context("renderScene"):
                rendergraph.renderScene(self.renderGraph)



    @property
    def fps(self):
        samples = 3
        if len(self.frameSamples) <= samples:
            return 0.0

        return (samples - 1) / (self.frameSamples[-1] - self.frameSamples[-samples])

    def rayAtPosition(self, x, y):
        """
        Given coordinates in screen space, return a ray in 3D space.

        Parameters:
            x and y are coordinates local to this QWidget

        :rtype: Ray
        """

        p0, p1 = self.pointsAtPositions((x, y, 0.0), (x, y, 0.1))
        return Ray(p0, (p1 - p0).normalize())

    def rayAtCenter(self):
        return self.rayAtPosition(self.width()/2, self.height()/2)

    def pointsAtPositions(self, *screenPoints):
        w = float(self.width())
        h = float(self.height())
        matrix = self.matrixNode.projection * self.matrixNode.modelview
        inverse, ok = matrix.inverted()

        if not ok or 0 in (w, h):
            return [Vector(0, 0, 0) for i in screenPoints]

        def _unproject():
            for x, y, z in screenPoints:
                x = float(x)
                y = float(y)
                y = h - y
                x = 2 * x / w - 1
                y = 2 * y / h - 1

                def v(p):
                    return Vector(p.x(), p.y(), p.z())

                yield v(inverse.map(QtGui.QVector3D(x, y, z)))

        return list(_unproject())

    def unprojectAtHeight(self, x, y, h):
        """
        Given coordinates in screen space, find the corresponding point in 3D space.

        Like rayAtPosition, but the third parameter is a height value in 3D space.
        """
        ray = self.rayAtPosition(x, y)
        return ray.atHeight(h)

    _chunkIter = None

    def resetLoadOrder(self):
        self._chunkIter = None

    def makeChunkIter(self):
        x, y, z = self.viewCenter()
        return iterateChunks(x, z, 1 + max(self.width() * self.scale, self.height() * self.scale) // 32)

    def requestChunk(self):
        if self._chunkIter is None:
            self._chunkIter = self.makeChunkIter()
        try:
            for c in self._chunkIter:
                if self.worldScene.wantsChunk(c):
                    return c
        except StopIteration:
            pass

    def wantsChunk(self, c):
        if not self.worldScene.wantsChunk(c):
            return False

        if hasattr(self, 'frustum'):
            point = [
                c[0] * 16 + 8,
                self.dimension.bounds.miny + self.dimension.bounds.height / 2,
                c[1] * 16 + 8,
                1.0
            ]
            return self.frustum.visible1(point=point, radius=self.dimension.bounds.height / 2)

        return True

    def recieveChunk(self, chunk):
        t = time.time()
        if self.lastAutoUpdate + self.autoUpdateInterval < t:
            self.lastAutoUpdate = t
            log.debug("update(): receivedChunk %s %s", self, chunk)
            self.update()

        with profiler.getProfiler().context("preloadCulling"):
            if hasattr(self, 'frustum'):
                cx, cz = chunk.chunkPosition
                points = [(cx * 16 + 8, h + 8, cz * 16 + 8, 1.0)
                          for h in chunk.sectionPositions()]
                points = numpy.array(points)

                visibleSections = self.frustum.visible(points, radius=8 * math.sqrt(2))
            else:
                visibleSections = None

        return self.worldScene.workOnChunk(chunk, visibleSections)

    def chunkInvalid(self, (cx, cz)):
        self.worldScene.invalidateChunk(cx, cz)
        self.resetLoadOrder()


def boxFaceUnderCursor(box, mouseRay):
    """
    Find the nearest face of the given bounding box that intersects with the given mouse ray
    and return (point, face)
    """
    nearPoint, mouseVector = mouseRay

    intersections = rayIntersectsBox(box, mouseRay)
    if intersections is None:
        return None, None

    point, face = intersections[0]

    # if the point is near the edge of the face, and the edge is facing away,
    # return the away-facing face

    dim = face.dimension

    dim1 = (dim + 1) % 3
    dim2 = (dim + 2) % 3

    # determine if a click was within self.edge_factor of the edge of a selection box side. if so, click through
    # to the opposite side
    edge_factor = 0.1

    for d in dim1, dim2:
        if not isinstance(d, int):
            assert False
        edge_width = box.size[d] * edge_factor
        faceNormal = [0, 0, 0]
        cameraBehind = False

        if point[d] - box.origin[d] < edge_width:
            faceNormal[d] = -1
            cameraBehind = nearPoint[d] - box.origin[d] > 0
        if point[d] - box.maximum[d] > -edge_width:
            faceNormal[d] = 1
            cameraBehind = nearPoint[d] - box.maximum[d] < 0

        if numpy.dot(faceNormal, mouseVector) > 0 or cameraBehind:
            # the face adjacent to the clicked edge faces away from the cam
            # xxxx this is where to allow iso views in face-on angles to grab edges
            # xxxx also change face highlight node to highlight this area
            return intersections[1] if len(intersections) > 1 else intersections[0]

    return point, face


def findBlockFace(level, point):
    """
    Examines the level at the given point and finds which exposed face of the block
    should be highlighted. It finds the side of the block that the floating-point coordinate
    is nearest to and then checks nearby blocks to see if that face is exposed. If not, it returns
    the exposed face it thinks is most appropriate for the given point.

    Returns a (pos, Face) pair or None if one couldn't be found"""

    direction = [0, 0, 0]

    try:
        blockPosition = list(point.intfloor())
    except ValueError:
        return None  # catch NaNs
    blockPosition[1] = max(0, blockPosition[1])

    # Compute a vector pointing from the center of the block to the point
    # on its surface.

    faceVector = ((point[0] - (blockPosition[0] + 0.5)),
                  (point[1] - (blockPosition[1] + 0.5)),
                  (point[2] - (blockPosition[2] + 0.5))
    )

    av = map(abs, faceVector)

    longAxis = av.index(max(av))
    delta = faceVector[longAxis]
    if delta < 0:
        direction[longAxis] = -1
    else:
        direction[longAxis] = 1

    # Find a list of all directions in which this block has an exposed face
    # In this case we only check whether the block IDs are different. This could be improved.
    potentialOffsets = []

    try:
        block = level.getBlock(*blockPosition)
    except (EnvironmentError, exceptions.LevelFormatError):
        return Vector(*blockPosition), faces.FaceYIncreasing

    if block.internalName == "minecraft:snow_layer":
        potentialOffsets.append((0, 1, 0))
    else:
        for face, offsets in faces.faceDirections:
            point = map(lambda a, b: a + b, blockPosition, offsets)
            try:
                neighborBlock = level.getBlock(*point)
                if block != neighborBlock:
                    potentialOffsets.append(offsets)
            except (EnvironmentError, exceptions.LevelFormatError):
                pass

    # If the computed direction doesn't have an exposed face, check each component of the original
    # face vector to see if the corresponding face is exposed
    for i in range(2):
        if tuple(direction) not in potentialOffsets:
            av[longAxis] = 0
            longAxis = av.index(max(av))
            direction = [0, 0, 0]
            delta = faceVector[longAxis]
            if delta < 0:
                direction[longAxis] = -1
            else:
                direction[longAxis] = 1

    if tuple(direction) not in potentialOffsets:
        if len(potentialOffsets):
            direction = potentialOffsets[0]
        else:
            # use the top face as a fallback
            direction = [0, 1, 0]

    direction = tuple(direction)
    for face, d in faces.faceDirections:
        if direction == d:
            break

    return Vector(*blockPosition), face


def iterateChunks(x, z, radius):
    """
    Yields a list of chunk positions starting from the center and going outward in a square spiral pattern.

    :param x: center block position
    :param z: center block position
    :param radius: radius, in chunks
    :type radius: int
    :return:
    :rtype:
    """
    cx = int(math.floor(x)) >> 4
    cz = int(math.floor(z)) >> 4

    yield (cx, cz)

    step = dir = 1

    while True:
        for i in range(step):
            cx += dir
            yield (cx, cz)

        for i in range(step):
            cz += dir
            yield (cx, cz)

        step += 1
        if step > radius * 2:
            raise StopIteration

        dir = -dir


class WorldViewInfo(InfoPanel):
    def __init__(self, **kwargs):
        InfoPanel.__init__(self,
                           ['centerPoint', 'mouseBlockPos', 'mouseRay', 'worldMeshVertexSize',
                            'worldMeshChunks'],
                           ['viewportMoved', 'cursorMoved'],
                           **kwargs)

    @property
    def worldMeshVertexSize(self):
        # size = worldMeshVertexSize(self.object.worldMesh)
        # return "%0.2f MB" % (size / 1000000)
        return "-1"

    @property
    def worldMeshChunks(self):
        try:
            return "%s" % len(self.object.worldScene.chunkRenderInfo)
        except AttributeError as e:
            return "%s" % e


class WorldCursorInfo(InfoPanel):
    def __init__(self, **kwargs):
        super(WorldCursorInfo, self).__init__(['blockPos', 'mouseBlockFace', 'describeBlock', 'describeAdjacent'],
                                              ['cursorMoved'], **kwargs)

        #InfoPanel.__init__(self,
        #                   ['mouseBlockPos', 'mouseBlockFace', 'describeBlock', 'describeAdjacent'],
        #                   ['cursorMoved'], **kwargs)

    @property
    def blockPos(self):
        pos = self.object.mouseBlockPos
        if pos is not None:
            x, y, z = pos
            cx = x >> 4
            cy = y >> 4
            cz = z >> 4
            return "%s (cx=%d, cy=%d, cz=%d)" % (pos, cx, cy, cz)
        else:
            return "(None)"

    @property
    def describeBlock(self):
        pos = self.object.mouseBlockPos
        if pos is not None:
            return "%s: %s" % (pos, self.describe(pos))
        else:
            return "(None)"

    dirs = dict(faces.faceDirections)

    @property
    def describeAdjacent(self):
        pos = self.object.mouseBlockPos
        if pos is not None:
            face = self.object.mouseBlockFace
            pos += self.dirs[face]
            return "%s: %s" % (pos, self.describe(pos))
        else:
            return "(None)"

    def describe(self, pos):
        """

        :type pos: Vector or tuple
        :return:
        :rtype:
        """
        dim = self.object.dimension
        try:
            result = dim.getBlocks(pos[0], pos[1], pos[2],
                                   return_Data=True,
                                   return_BlockLight=True,
                                   return_SkyLight=True)
            if result.Data is not None:
                data = result.Data[0]
            else:
                data = 0
            if result.BlockLight is not None:
                bl = result.BlockLight[0]
            else:
                bl = "N/A"
            if result.SkyLight is not None:
                sl = result.SkyLight[0]
            else:
                sl = "N/A"

            desc = "\tID: %s\tData: %s\tLight: %s\tSkyLight: %s" % (
                result.Blocks[0],
                data, bl, sl,
            )

            cPos = pos.chunkPos()
            chunk = dim.getChunk(cPos[0], cPos[2])
            if chunk.HeightMap is not None:
                ix, iz = pos[0] & 0xf, pos[2] & 0xf
                #log.info("HeightMap (%s:%s): \n%s", cPos, (ix, iz), chunk.HeightMap)
                desc += "\tHeightMap(%s:%s): %d" % (cPos, (ix, iz), chunk.HeightMap[iz, ix])

            desc += "\tName: %s" % dim.blocktypes[result.Blocks[0], result.Data[0]].displayName
            return desc
        except ChunkNotPresent:
            return "Chunk not present."
        except (EnvironmentError, LevelFormatError) as e:
            return "Error describing block: %r" % e
        except Exception as e:
            log.exception("Error describing block: %r", e)
            return "Error describing block: %r" % e
