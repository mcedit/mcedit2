"""
    imports
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtCore, QtGui
from PySide.QtCore import Qt
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.scenegraph.matrix import TranslateNode, RotateNode
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.worldloader import WorldLoader
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

    def __init__(self, pendingImport, textureAtlas):
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
        dim = pendingImport.sourceDim

        # positionTranslateNode contains the non-transformed preview of the imported
        # object, including its world scene. This preview will be rotated model-wise
        # while the user is dragging the rotate controls.

        self.positionTranslateNode = TranslateNode()
        self.rotateNode = Rotate3DNode()
        self.addChild(self.positionTranslateNode)
        self.positionTranslateNode.addChild(self.rotateNode)

        self.rotateNode.setAnchor(self.pendingImport.selection.size * 0.5)

        # worldSceneTranslateNode is contained by positionTranslateNode, and
        # serves to translate the world scene back to 0, 0, 0 so the positionTranslateNode
        # can translate by the current position.

        self.worldSceneTranslateNode = TranslateNode()
        self.worldScene = WorldScene(dim, textureAtlas, bounds=pendingImport.selection)
        self.worldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer

        # transformedWorldTranslateNode contains the transformed preview of the imported
        # object, including a world scene that displays the object wrapped by a
        # DimensionTransform.

        self.transformedWorldTranslateNode = TranslateNode()
        self.transformedWorldScene = None
        self.addChild(self.transformedWorldTranslateNode)

        self.worldSceneTranslateNode.translateOffset = -self.pendingImport.selection.origin
        self.worldSceneTranslateNode.addChild(self.worldScene)
        self.rotateNode.addChild(self.worldSceneTranslateNode)

        # handleNode displays a bounding box that can be moved around, and responds
        # to mouse events.

        box = BoundingBox(pendingImport.importPos, pendingImport.importBounds.size)

        self.handleNode = BoxHandle()
        self.handleNode.bounds = box
        self.handleNode.resizable = False

        self.updateTransformedScene()
        self.basePosition = pendingImport.basePosition

        self.handleNode.boundsChanged.connect(self.handleBoundsChanged)
        self.handleNode.boundsChangedDone.connect(self.handleBoundsChangedDone)

        self.addChild(self.handleNode)

        # loads the non-transformed world scene asynchronously.
        self.loader = WorldLoader(self.worldScene,
                                  list(pendingImport.selection.chunkPositions()))
        self.loader.startLoader()

        self.pendingImport.positionChanged.connect(self.setPosition)
        self.pendingImport.rotationChanged.connect(self.setRotation)

    # Emitted when the user finishes dragging the box handle and releases the mouse
    # button. Arguments are (newPosition, oldPosition).
    importMoved = QtCore.Signal(object, object)

    def handleBoundsChangedDone(self, bounds, oldBounds):
        point = self.getBaseFromTransformed(bounds.origin)
        oldPoint = self.getBaseFromTransformed(oldBounds.origin)
        if point != oldPoint:
            self.importMoved.emit(point, oldPoint)

    def handleBoundsChanged(self, bounds):
        point = self.getBaseFromTransformed(bounds.origin)
        if self.basePosition != point:
            self.basePosition = point

    def getBaseFromTransformed(self, point):
        offset = self.pendingImport.basePosition - self.pendingImport.importPos
        return point + offset

    def setPreviewRotation(self, rots):
        self.rotateNode.visible = True
        self.worldSceneTranslateNode.visible = True
        self.transformedWorldTranslateNode.visible = False
        self.rotateNode.setRotation(rots)

    def setRotation(self, rots):
        self.updateTransformedScene()
        self.updateBoxHandle()
        self.rotateNode.setRotation(rots)

    def updateTransformedScene(self):
        if self.pendingImport.transformedDim is not None:
            log.info("Showing transformed scene")
            self.rotateNode.visible = False
            self.worldSceneTranslateNode.visible = False
            self.transformedWorldTranslateNode.visible = True

            if self.transformedWorldScene:
                self.transformedWorldTranslateNode.removeChild(self.transformedWorldScene)

            self.transformedWorldScene = WorldScene(self.pendingImport.transformedDim,
                                                    self.textureAtlas)
            self.transformedWorldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer
            self.transformedWorldTranslateNode.addChild(self.transformedWorldScene)

            self.updateTransformedSceneOffset()

            cPos = list(self.pendingImport.transformedDim.chunkPositions())
            self.loader = WorldLoader(self.transformedWorldScene,
                                      cPos)
            self.loader.startLoader()

        else:
            log.info("Hiding transformed scene")
            self.rotateNode.visible = True
            self.worldSceneTranslateNode.visible = True
            self.transformedWorldTranslateNode.visible = False
            if self.transformedWorldScene:
                self.transformedWorldTranslateNode.removeChild(self.transformedWorldScene)
                self.transformedWorldScene = None

    def updateTransformedSceneOffset(self):
        self.transformedWorldTranslateNode.translateOffset = self.transformedPosition - self.pendingImport.importDim.bounds.origin

    @property
    def transformedPosition(self):
        return self.basePosition + self.pendingImport.importPos - self.pendingImport.basePosition

    @property
    def basePosition(self):
        return self.positionTranslateNode.translateOffset

    @basePosition.setter
    def basePosition(self, value):
        if value == self.positionTranslateNode.translateOffset:
            return

        self.positionTranslateNode.translateOffset = Vector(*value)
        self.updateTransformedSceneOffset()
        self.updateBoxHandle()

    def setPosition(self, pos):
        self.basePosition = pos

    def updateBoxHandle(self):
        if self.transformedWorldScene is None:
            bounds = BoundingBox(self.basePosition, self.pendingImport.bounds.size)
        else:
            origin = self.transformedPosition
            bounds = BoundingBox(origin, self.pendingImport.importBounds.size)
        #if self.handleNode.bounds.size != bounds.size:
        self.handleNode.bounds = bounds

    # --- Mouse events ---

    # inherit from BoxHandle?
    def mouseMove(self, event):
        self.handleNode.mouseMove(event)

    def mousePress(self, event):
        self.handleNode.mousePress(event)

    def mouseRelease(self, event):
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
        self.positionChanged.emit(self._pos)

    @property
    def importPos(self):
        if self.transformedDim is None:
            return self.basePosition
        return self.basePosition + self.transformedDim.bounds.origin - self.selection.origin

    @importPos.setter
    def importPos(self, pos):
        if self.transformedDim is None:
            self.basePosition = pos
        else:
            self.basePosition = pos - self.transformedDim.bounds.origin + self.selection.origin

    @property
    def importDim(self):
        if self.transformedDim is not None:
            return self.transformedDim
        else:
            return self.sourceDim

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        if self._rotation == value:
            return
        self._rotation = Vector(*value)
        self.updateTransform()
        self.rotationChanged.emit(self._rotation)

    @property
    def scale(self):
        return self._rotation

    @scale.setter
    def scale(self, value):
        if self._scale == value:
            return
        self._scale = Vector(*value)
        self.scaleChanged.emit(self._scale)
        self.updateTransform()

    def updateTransform(self):
        if self.rotation == (0, 0, 0) and self.scale == (0, 0, 0):
            self.transformedDim = None
        else:
            selectionDim = SelectionTransform(self.sourceDim, self.selection)
            self.transformedDim = DimensionTransform(selectionDim, self.rotateAnchor, *self.rotation)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (
            self.__class__.__name__, self.sourceDim, self.selection, self.basePosition)

    @property
    def bounds(self):
        return BoundingBox(self.basePosition, self.selection.size)

    @property
    def importBounds(self):
        if self.transformedDim is not None:
            size = self.transformedDim.bounds.size
        else:
            size = self.selection.size
        return BoundingBox(self.importPos, size)


class Rotate3DNode(Node):
    def __init__(self):
        super(Rotate3DNode, self).__init__()
        self.anchorNode = TranslateNode()
        self.rotXNode = RotateNode(axis=(1, 0, 0))
        self.rotYNode = RotateNode(axis=(0, 1, 0))
        self.rotZNode = RotateNode(axis=(0, 0, 1))
        self.recenterNode = TranslateNode()

        super(Rotate3DNode, self).addChild(self.anchorNode)
        self.anchorNode.addChild(self.rotZNode)
        self.rotZNode.addChild(self.rotYNode)
        self.rotYNode.addChild(self.rotXNode)
        self.rotXNode.addChild(self.recenterNode)

    def addChild(self, node):
        self.recenterNode.addChild(node)

    def removeChild(self, node):
        self.recenterNode.removeChild(node)

    def setRotation(self, rots):
        rx, ry, rz = rots
        self.rotXNode.degrees = rx
        self.rotYNode.degrees = ry
        self.rotZNode.degrees = rz

    def setAnchor(self, point):
        self.anchorNode.translateOffset = point
        self.recenterNode.translateOffset = -point