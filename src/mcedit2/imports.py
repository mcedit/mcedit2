"""
    imports
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtCore, QtGui
from PySide.QtCore import Qt
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering.depths import DepthOffsets
from mcedit2.rendering.scenegraph.matrix import Translate, Rotate, Scale
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mceditlib.export import extractSchematicFromIter
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox
from mceditlib.transform import SelectionTransform, DimensionTransform

log = logging.getLogger(__name__)

class PendingImportsGroup(QtCore.QObject):
    def __init__(self):
        super(PendingImportsGroup, self).__init__()

        self.pendingImports = []

        self.pendingImportNodes = {}

    def addPendingImport(self, pendingImport):
        log.info("Added import: %s", pendingImport)
        self.pendingImports.append(pendingImport)
        item = QtGui.QStandardItem()
        item.setEditable(False)
        item.setText(pendingImport.text)
        item.setData(pendingImport, Qt.UserRole)
        self.importsListModel.appendRow(item)
        self.importsListWidget.setCurrentIndex(self.importsListModel.index(self.importsListModel.rowCount()-1, 0))
        node = self.pendingImportNodes[pendingImport] = PendingImportNode(pendingImport, self.editorSession.textureAtlas)
        node.importMoved.connect(self.importDidMove)

        self.overlayNode.addChild(node)
        self.currentImport = pendingImport

    def removePendingImport(self, pendingImport):
        index = self.pendingImports.index(pendingImport)
        self.pendingImports.remove(pendingImport)
        self.importsListModel.removeRows(index, 1)
        self.currentImport = self.pendingImports[-1] if len(self.pendingImports) else None
        node = self.pendingImportNodes.pop(pendingImport)
        if node:
            self.overlayNode.removeChild(node)
    #
    # def listClicked(self, index):
    #     item = self.importsListModel.itemFromIndex(index)
    #     pendingImport = item.data(Qt.UserRole)
    #     self.currentImport = pendingImport

    def listDoubleClicked(self, index):
        item = self.importsListModel.itemFromIndex(index)
        pendingImport = item.data(Qt.UserRole)
        self.editorSession.editorTab.currentView().centerOnPoint(pendingImport.bounds.center)


class PendingImportNode(Node, QtCore.QObject):
    __node_id_counter = 0

    def __init__(self, pendingImport, textureAtlas, hasHandle=True):
        """
        A scenegraph node displaying an object that will be imported later, including
        live and deferred views of the object with transformed items, and a BoxHandle
        for moving the item.

        Parameters
        ----------

        pendingImport: PendingImport
            The object to be imported. The PendingImportNode responds to changes in this
            object's position, rotation, and scale.
        textureAtlas: TextureAtlas
            The textures and block models used to render the preview of the object.
        hasHandle: bool
            True if this import node should have a user-interactive BoxHandle associated
            with it. This is False for the extra copies displayed by a repeated clone.

        Attributes
        ----------

        basePosition: Vector
            The pre-transform position of the pending import. This is equal to
            `self.pendingImport.basePosition` except when the node is currently being
            dragged.
        transformedPosition: Vector
            The post-transform position of the pending import. This is equal to
            `self.pendingImport.importPos` except when the node is currently being
            dragged, scaled, or rotated.
        """
        super(PendingImportNode, self).__init__()

        self.textureAtlas = textureAtlas
        self.pendingImport = pendingImport
        self.hasHandle = hasHandle

        dim = pendingImport.sourceDim

        self.transformedPosition = Vector(0, 0, 0)

        # worldScene is contained by rotateNode, and
        # translates the world scene back to 0, 0, 0 so the rotateNode can
        # rotate it around the anchor, and the plainSceneNode can translate
        # it to the current position.

        self.worldScene = WorldScene(dim, textureAtlas, bounds=pendingImport.selection)
        self.worldScene.depthOffset.depthOffset = DepthOffsets.PreviewRenderer

        self.worldSceneTranslate = Translate(-self.pendingImport.selection.origin)
        self.worldScene.addState(self.worldSceneTranslate)

        # rotateNode is used to rotate the non-transformed preview during live rotation

        self.rotateNode = Rotate3DNode()
        self.rotateNode.setAnchor(self.pendingImport.selection.size * 0.5)
        self.rotateNode.addChild(self.worldScene)

        self.scaleNode = Scale3DNode()
        self.scaleNode.setAnchor(self.pendingImport.selection.size * 0.5)
        self.scaleNode.addChild(self.rotateNode)

        # plainSceneNode contains the non-transformed preview of the imported
        # object, including its world scene. This preview will be rotated model-wise
        # while the user is dragging the rotate controls.

        self.plainSceneNode = Node("plainScene")
        self.positionTranslate = Translate()
        self.plainSceneNode.addState(self.positionTranslate)
        self.plainSceneNode.addChild(self.scaleNode)

        self.addChild(self.plainSceneNode)

        # transformedSceneNode contains the transformed preview of the imported
        # object, including a world scene that displays the object wrapped by a
        # DimensionTransform.

        self.transformedSceneNode = Node("transformedScene")
        self.transformedSceneTranslate = Translate()
        self.transformedSceneNode.addState(self.transformedSceneTranslate)

        self.transformedWorldScene = None
        self.addChild(self.transformedSceneNode)

        box = BoundingBox(pendingImport.importPos, pendingImport.importBounds.size)

        if hasHandle:
            # handleNode displays a bounding box that can be moved around, and responds
            # to mouse events.
            self.handleNode = BoxHandle()
            self.handleNode.bounds = box
            self.handleNode.resizable = False
            self.boxNode = None
        else:
            # boxNode displays a plain, non-movable bounding box
            self.boxNode = SelectionBoxNode()
            self.boxNode.wireColor = (1, 1, 1, .2)
            self.boxNode.filled = False
            self.handleNode = None
            self.addChild(self.boxNode)

        self.updateTransformedScene()
        self.basePosition = pendingImport.basePosition

        if hasHandle:
            self.handleNode.boundsChanged.connect(self.handleBoundsChanged)
            self.handleNode.boundsChangedDone.connect(self.handleBoundsChangedDone)

            self.addChild(self.handleNode)

        # loads the non-transformed world scene asynchronously.
        self.loader = WorldLoader(self.worldScene,
                                  list(pendingImport.selection.chunkPositions()))
        self.loader.startLoader(0.1 if self.hasHandle else 0.0)

        self.pendingImport.positionChanged.connect(self.setPosition)
        self.pendingImport.rotationChanged.connect(self.setRotation)
        self.pendingImport.scaleChanged.connect(self.setScale)

    # Emitted when the user finishes dragging the box handle and releases the mouse
    # button. Arguments are (newPosition, oldPosition).
    importMoved = QtCore.Signal(object, object)

    # Emitted while the user is dragging the box handle. Argument is the box origin.
    importIsMoving = QtCore.Signal(object)

    def handleBoundsChangedDone(self, bounds, oldBounds):
        point = self.getBaseFromTransformed(bounds.origin)
        oldPoint = self.getBaseFromTransformed(oldBounds.origin)
        if point != oldPoint:
            self.importMoved.emit(point, oldPoint)

    def handleBoundsChanged(self, bounds):
        log.info("handleBoundsChanged: %s", bounds)
        self.setPreviewBasePosition(bounds.origin)

    def setPreviewBasePosition(self, origin):
        point = self.getBaseFromTransformed(origin)
        if self.basePosition != point:
            self.basePosition = point
            self.importIsMoving.emit(point)

    def getBaseFromTransformed(self, point):
        return point - self.pendingImport.transformOffset

    def setPreviewRotation(self, rots):
        self.plainSceneNode.visible = True
        self.transformedSceneNode.visible = False
        self.rotateNode.setRotation(rots)

    def setRotation(self, rots):
        self.updateTransformedScene()
        self.updateBoxHandle()
        self.rotateNode.setRotation(rots)

    def setPreviewScale(self, scale):
        self.plainSceneNode.visible = True
        self.transformedSceneNode.visible = False
        self.scaleNode.setScale(scale)

    def setScale(self, scale):
        self.updateTransformedScene()
        self.updateBoxHandle()
        self.scaleNode.setScale(scale)

    def updateTransformedScene(self):
        if self.pendingImport.transformedDim is not None:
            log.info("Showing transformed scene")
            self.plainSceneNode.visible = False
            self.transformedSceneNode.visible = True

            if self.transformedWorldScene:
                self.transformedSceneNode.removeChild(self.transformedWorldScene)

            self.transformedWorldScene = WorldScene(self.pendingImport.transformedDim,
                                                    self.textureAtlas)
            self.transformedWorldScene.depthOffset.depthOffset = DepthOffsets.PreviewRenderer
            self.transformedSceneNode.addChild(self.transformedWorldScene)

            self.updateTransformedPosition()

            cPos = list(self.pendingImport.transformedDim.chunkPositions())
            self.loader = WorldLoader(self.transformedWorldScene,
                                      cPos)

            # ALERT!: self.hasHandle is overloaded with the meaning:
            #  "not the first clone in a repeated clone"
            self.loader.startLoader(0.1 if self.hasHandle else 0.0)

        else:
            log.info("Hiding transformed scene")
            self.plainSceneNode.visible = True
            self.transformedSceneNode.visible = False
            if self.transformedWorldScene:
                self.transformedSceneNode.removeChild(self.transformedWorldScene)
                self.transformedWorldScene = None

    def updateTransformedPosition(self):
        self.transformedPosition = self.basePosition + self.pendingImport.transformOffset
        self.transformedSceneTranslate.translateOffset = self.transformedPosition - self.pendingImport.importDim.bounds.origin

    def updateBoxHandle(self):
        if self.transformedWorldScene is None:
            bounds = BoundingBox(self.basePosition, self.pendingImport.bounds.size)
        else:
            origin = self.transformedPosition
            bounds = BoundingBox(origin, self.pendingImport.importBounds.size)
        #if self.handleNode.bounds.size != bounds.size:
        if self.hasHandle:
            self.handleNode.bounds = bounds
        else:
            self.boxNode.selectionBox = bounds

    @property
    def basePosition(self):
        return self.positionTranslate.translateOffset

    @basePosition.setter
    def basePosition(self, value):
        value = Vector(*value)
        if value == self.positionTranslate.translateOffset:
            return

        self.positionTranslate.translateOffset = value
        self.updateTransformedPosition()
        self.updateBoxHandle()

    def setPosition(self, pos):
        self.basePosition = pos

    # --- Mouse events ---

    # inherit from BoxHandle?
    def mouseMove(self, event):
        if not self.hasHandle:
            return
        self.handleNode.mouseMove(event)

    def mousePress(self, event):
        if not self.hasHandle:
            return
        self.handleNode.mousePress(event)

    def mouseRelease(self, event):
        if not self.hasHandle:
            return
        self.handleNode.mouseRelease(event)


class PendingImport(QtCore.QObject):
    """
    An object representing a schematic, etc that is currently being imported and can be
    moved/rotated/scaled by the user.

    Parameters
    ----------

    sourceDim: WorldEditorDimension
        The object that will be imported.
    basePosition: Vector
        The position in the currently edited world where the object will be imported.
    selection: SelectionBox
        Defines the portion of sourceDim that will be imported. For importing
        .schematic files, this is usually the schematic's bounds. For importing/moving
        a selected part of a world, this is the shaped selection created by the
        Select tool.
    text: unicode
        A user-readable name for this import to be displayed in the "pending imports"
        list, when multiple-importing is enabled.
    isMove: bool
        A flag that tells whether the imported object is being moved or copied. If it is
        being moved, the previous position of the object is filled with air and cleared
        of entities.

    Attributes
    ----------

    importPos: Vector
        The effective position where the object is to be imported. When the
        PendingImport's rotation or scale is the default, this will be the
        same as `self.basePosition`, otherwise it will be the position where the transformed
        object will be imported. Changing this attribute will also change `self.basePosition`
        to the pre-transform position accordingly.

    importDim: WorldEditorDimension
        The effective dimension to be imported. When the rotation or scale is the
        default, this will be the same as `self.sourceDim`; otherwise, it will be a
        TransformedDimension, which is a read-only proxy that acts as a scaled and
        rotated form of `self.sourceDim`.

    rotation: tuple of float
        The rotation transform to be applied during import, in the form
        (rotX, rotY, rotZ). Rotation is applied around the center point given
        by `self.rotateAnchor`

    scale: tuple of float
        The scale transform to be applied during import, in the form
        (rotX, rotY, rotZ). Scaling is applied around the center point given
        by `self.rotateAnchor`

    rotateAnchor: Vector
        The anchor point that acts as the "center" when applying rotation
        and scale transforms, in source coordinates. By default,
        this is the center of `self.selection`.

    bounds: BoundingBox
        The axis-aligned bounding box that completely encloses `self.selection`, moved
        to the position given by `self.basePosition`, in destination coordinates.

    importBounds: BoundingBox
        The axis-aligned bounding box that completely encloses the transformed dimension
        `self.transformedDim` in destination coordinates.

    """
    def __init__(self, sourceDim, pos, selection, text, isMove=False):
        super(PendingImport, self).__init__()

        self.selection = selection
        self.text = text
        self._pos = pos
        self.sourceDim = sourceDim
        self.isMove = isMove
        self._rotation = (0, 0, 0)
        self._scale = (0, 0, 0)
        self.transformedDim = None

        self.transformOffset = Vector(0, 0, 0)
        self.importPos = Vector(0, 0, 0)
        self.importBounds = BoundingBox()

        self.updateImportPos()

        bounds = self.selection
        self.rotateAnchor = bounds.origin + bounds.size * 0.5

    positionChanged = QtCore.Signal(object)
    rotationChanged = QtCore.Signal(object)
    scaleChanged = QtCore.Signal(object)

    @property
    def basePosition(self):
        return self._pos

    @basePosition.setter
    def basePosition(self, value):
        if value == self._pos:
            return

        self._pos = Vector(*value)
        self.updateImportPos()
        self.positionChanged.emit(self._pos)

    def updateImportPos(self):
        if self.transformedDim is None:
            self.importPos = self.basePosition
            size = self.selection.size
        else:
            self.importPos = self.basePosition + self.transformOffset
            size = self.transformedDim.bounds.size

        self.importBounds = BoundingBox(self.importPos, size)

    @property
    def importDim(self):
        if self.transformedDim is not None:
            return self.transformedDim
        else:
            return self.sourceDim

    def getSourceForDim(self, destDim):
        if self.transformedDim is not None:
            selection = self.transformedDim.bounds
        else:
            selection = self.selection

        if destDim is self.sourceDim:
            sourceDim = self.importDim
            destBox = self.importBounds

            if self.transformedDim is not None:
                sourceBounds = sourceDim.bounds
            else:
                sourceBounds = self.selection
            # Use intermediate schematic only if source and destination overlap.
            if sourceBounds.intersect(destBox).volume:
                log.info("Move: using temporary")
                export = extractSchematicFromIter(sourceDim, selection)
                schematic = showProgress(self.tr("Copying..."), export)
                tempDim = schematic.getDimension()
                return tempDim, tempDim.bounds

        # Use source as-is
        return self.importDim, selection

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        value = tuple(value)
        if self._rotation == value:
            return
        self._rotation = value
        self.updateTransform()
        self.rotationChanged.emit(self._rotation)

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        if self._scale == value:
            return
        self._scale = Vector(*value)
        self.updateTransform()
        self.scaleChanged.emit(self._scale)

    def updateTransform(self):
        if self.rotation == (0, 0, 0) and self.scale == (1, 1, 1):
            self.transformedDim = None
            self.transformOffset = Vector(0, 0, 0)
        else:
            selectionDim = SelectionTransform(self.sourceDim, self.selection)
            self.transformedDim = DimensionTransform(selectionDim, self.rotateAnchor, self.rotation, self.scale)
            self.transformOffset = self.transformedDim.bounds.origin - self.selection.origin

        self.updateImportPos()

    def __repr__(self):
        return "%s(%r, %r, %r)" % (
            self.__class__.__name__, self.sourceDim, self.selection, self.basePosition)

    @property
    def bounds(self):
        return BoundingBox(self.basePosition, self.selection.size)


class Rotate3DNode(Node):
    def __init__(self):
        super(Rotate3DNode, self).__init__()
        self.anchor = Translate()
        self.rotX = Rotate(axis=(1, 0, 0))
        self.rotY = Rotate(axis=(0, 1, 0))
        self.rotZ = Rotate(axis=(0, 0, 1))
        self.recenter = Translate()

        self.addState(self.anchor)
        self.addState(self.rotZ)
        self.addState(self.rotY)
        self.addState(self.rotX)
        self.addState(self.recenter)

    def setRotation(self, rots):
        rx, ry, rz = rots
        self.rotX.degrees = rx
        self.rotY.degrees = ry
        self.rotZ.degrees = rz

    def setAnchor(self, point):
        self.anchor.translateOffset = point
        self.recenter.translateOffset = -point
        

class Scale3DNode(Node):
    def __init__(self):
        super(Scale3DNode, self).__init__()
        self.anchor = Translate()
        self.scale = Scale()
        self.recenter = Translate()

        self.addState(self.anchor)
        self.addState(self.scale)
        self.addState(self.recenter)

    def setScale(self, scale):
        self.scale.scale = scale

    def setAnchor(self, point):
        self.anchor.translateOffset = point
        self.recenter.translateOffset = -point