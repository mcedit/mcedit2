"""
    boxhandle
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtCore, QtGui
import numpy

from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.selection import SelectionBoxNode, SelectionFaceNode, boxFaceUnderCursor
from mceditlib import faces
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)


class BoxHandle(scenenode.Node, QtCore.QObject):
    # The face that was clicked on
    dragResizeFace = None

    # The dimension of the imaginary plane perpendicular to the clicked face
    # that the drag will move across
    dragResizeDimension = None
    dragResizePosition = None

    dragStartPoint = None
    dragStartFace = None

    dragStartMovePosition = None

    oldBounds = None

    hiliteFace = True

    _resizable = True
    modifier = QtCore.Qt.ShiftModifier

    isMoving = False
    isCreating = False
    isResizing = False

    classicSelection = False
    stickySelection = False

    isSticking = False

    def __init__(self):
        """
        A drawable, resizable box that can respond to mouse events. Emits boundsChanged
        whenever its bounding box changes, and emits boundsChangedDone when the
        mouse button is released.

        The handle initially has no box; the first mouse action will define
        the initial box with height=0. If a subsequent mouse action does not intersect
        the box, a new initial box will be created; otherwise, the existing box will be
        moved or resized.

        Mouse events must be forwarded to the handle using mousePress, mouseDrag, and
        mouseRelease.

        A modifier can be set (default Shift) to move the box instead of resizing it;
        or the `resizable` attribute can be set to False to always move the box. When
        `resizable` is False, new initial boxes cannot be created.

        :return:
        :rtype:
        """
        super(BoxHandle, self).__init__()
        self.boxNode = SelectionBoxNode()
        self.boxNode.filled = False
        self.faceDragNode = SelectionFaceNode()
        self.addChild(self.boxNode)
        self.addChild(self.faceDragNode)

    boundsChanged = QtCore.Signal(BoundingBox)

    # newBox, oldBox
    boundsChangedDone = QtCore.Signal(BoundingBox, BoundingBox)

    @property
    def bounds(self):
        return self.boxNode.selectionBox

    @bounds.setter
    def bounds(self, box):
        if box != self.boxNode.selectionBox:
            self.boxNode.selectionBox = box
            self.faceDragNode.selectionBox = box
    
    def changeBounds(self, box):
        # Call in response to user input, but not programmatic bounds change
        self.bounds = box
        self.boundsChanged.emit(box)

    def moveModifierDown(self, event):
        return event.modifiers() & self.modifier

    @property
    def resizable(self):
        return self._resizable

    @resizable.setter
    def resizable(self, value):
        assert value or self.bounds, "Sanity check: Non-resizable BoxHandle must have bounds."
        self._resizable = value

    # --- Resize helpers ---

    def dragResizePoint(self, ray):
        """
        Return a point representing the intersection between the mouse ray
        and an imaginary plane perpendicular to the dragged face

        :type ray: Ray
        :rtype: Vector
        """
        nearPoint, normal = ray

        dim = self.dragResizeDimension
        distance = self.dragResizePosition - nearPoint[dim]

        scale = distance / (normal[dim] or 0.0001)
        point = normal * scale + nearPoint
        return point

    def boxFromDragResize(self, box, ray):
        point = self.dragResizePoint(ray)

        side = self.dragResizeFace & 1
        dragdim = self.dragResizeFace >> 1

        origin, size = list(box.origin), list(box.size)
        if side:
            origin[dragdim] += size[dragdim]
        size[dragdim] = 0

        otherSide = BoundingBox(origin, size)
        origin[dragdim] = int(numpy.floor(point[dragdim] + 0.5))
        thisSide = BoundingBox(origin, size)

        return thisSide.union(otherSide)

    def boxFromDragSelect(self, event):
        """
        Create a flat selection from dragging the mouse outside the selection.

        Parameters
        ----------

        ray: mcedit2.util.geometry.Ray

        Returns
        -------

        box: BoundingBox
        """
        point = self.dragStartPoint
        face = self.dragStartFace
        size = [1, 1, 1]

        if self.classicSelection:
            endPoint = event.blockPosition
        else:
            ray = event.ray
            dim = face >> 1
            size[dim] = 0
            s = [0,0,0]

            if face & 1 == 0:
                s[dim] = 1
                point = point + s

            endPoint = ray.intersectPlane(dim, point[dim])

        startBox = BoundingBox(point, size)
        endBox = BoundingBox(endPoint.intfloor(), size)

        return startBox.union(endBox)

    # --- Resize ---

    def beginResize(self, event):
        log.debug("beginResize")
        point, face = boxFaceUnderCursor(self.bounds, event.ray)

        if face is not None:
            self.dragResizeFace = face
            # Choose a dimension perpendicular to the dragged face
            # Try not to pick a dimension close to edge-on with the view vector
            dim = ((face.dimension + 1) % 3)

            dim1 = (dim+1) % 3

            vector = event.view.cameraVector.abs()
            if vector[dim1] > vector[dim]:
                dim = dim1

            self.dragResizeDimension = dim
            self.dragResizePosition = point[self.dragResizeDimension]
            self.oldBounds = self.bounds
            self.isResizing = True
            return True
        else:
            # Didn't hit - start new selection
            self.changeBounds(None)

    def continueResize(self, event):
        if self.oldBounds is None:
            return

        # Hilite face being dragged
        newBox = self.boxFromDragResize(self.oldBounds, event.ray)
        self.faceDragNode.selectionBox = newBox
        self.faceDragNode.visible = True

        # Update selection box to resized size in progress
        newBox = self.boxFromDragResize(self.oldBounds, event.ray)
        self.changeBounds(newBox)

    def endResize(self, event):
        if self.oldBounds is None:
            return

        log.debug("endResize")
        self.bounds = self.boxFromDragResize(self.oldBounds, event.ray)
        oldBounds = self.oldBounds
        self.oldBounds = None
        self.dragResizeFace = None
        self.faceDragNode.visible = False
        self.isResizing = False
        self.boundsChangedDone.emit(self.bounds, oldBounds)

    # --- Create ---

    def beginCreate(self, event):
        # If the distance to the block is too far, face selection becomes inconsistent
        # and aggravating. Use YIncreasing if it is more than 50 blocks away.
        distance = (event.blockPosition - event.ray.point).length()

        self.dragStartPoint = event.blockPosition
        self.dragStartFace = faces.FaceYIncreasing if distance > 50 else event.blockFace
        self.isCreating = True

    def continueCreate(self, event):
        # Show new box being dragged out
        newBox = self.boxFromDragSelect(event)
        self.changeBounds(newBox)

    def endCreate(self, event):
        newBox = self.boxFromDragSelect(event)
        self.isCreating = False
        self.dragStartPoint = None
        self.dragStartFace = None

        self.bounds = newBox
        self.boundsChangedDone.emit(newBox, None)

    # --- Move helpers ---


    def dragMovePoint(self, ray):
        """
        Return a point representing the intersection between the mouse ray
         and an imaginary plane coplanar to the dragged face

        :type ray: Ray
        :rtype: Vector
        """
        dim = self.dragStartFace.dimension
        return ray.intersectPlane(dim, self.dragStartPoint[dim])

    # --- Move ---

    def beginMove(self, event):
        if self.bounds is None:
            return

        point, face = boxFaceUnderCursor(self.bounds, event.ray)
        self.dragStartFace = face
        self.dragStartPoint = point
        self.dragStartMovePosition = self.bounds.origin
        self.oldBounds = self.bounds
        self.isMoving = True

    def continueMove(self, event):
        if self.bounds is None:
            return

        if self.dragStartFace is None:
            return

        delta = self.dragMovePoint(event.ray) - self.dragStartPoint
        movePosition = self.dragStartMovePosition + map(int, delta)
        self.bounds = BoundingBox(movePosition, self.bounds.size)

    def endMove(self, event):
        if self.bounds is None:
            return

        self.boundsChangedDone.emit(self.bounds, self.oldBounds)
        self.dragStartFace = None
        self.isMoving = False

    # --- Update ---

    def updateMouseHover(self, event):
        """
        Update visuals for the mouse hovering over this box.
        """
        # Hilite face cursor is over
        if self.bounds is None:
            return
        point, face = boxFaceUnderCursor(self.bounds, event.ray)
        if face is not None:
            self.faceDragNode.visible = True
            self.faceDragNode.face = face
            self.faceDragNode.selectionBox = self.bounds
        else:
            self.faceDragNode.visible = False
        if self.moveModifierDown(event):
            self.faceDragNode.color = self._moveFaceColor
            self.faceDragNode.wireColor = self._moveFaceWireColor
        else:
            self.faceDragNode.color = self._resizeFaceColor
            self.faceDragNode.wireColor = self._resizeFaceWireColor

    _moveFaceColor = (0.3, 0.9, 0.3, 0.3)
    _moveFaceWireColor = (0.3, 0.9, 0.3, 0.8)
    _resizeFaceColor = (0.3, 0.6, 0.9, 0.3)
    _resizeFaceWireColor = (0.3, 0.6, 0.9, 0.8)

    # --- Mouse events ---

    def mousePress(self, event):
        if self.moveModifierDown(event) or not self.resizable:
            self.beginMove(event)
        elif self.resizable:

            # Get ready to start new selection
            if self.bounds is None:
                if self.stickySelection:
                    if not self.isSticking:
                        self.isSticking = True
                        self.beginCreate(event)
                else:
                    self.beginCreate(event)

            else:
                if self.isSticking:
                    self.isSticking = False
                    self.endCreate(event)
                    self.ignoreNextRelease = True
                else:
                    self.beginResize(event)

    def mouseMove(self, event):
        # Called whether or not the mouse button is held.
        if self.isMoving:
            self.continueMove(event)
        elif self.resizable:
            if self.isCreating:
                self.continueCreate(event)

            if self.isResizing:
                self.continueResize(event)

        if self.hiliteFace and not self.isMoving:
            self.updateMouseHover(event)

    ignoreNextRelease = False

    def mouseRelease(self, event):
        if self.ignoreNextRelease:
            self.ignoreNextRelease = False
            return

        if self.isMoving:
            self.endMove(event)
        elif self.resizable:
            if self.isCreating:
                if not self.stickySelection:
                    self.endCreate(event)

            elif self.isResizing:
                self.endResize(event)


