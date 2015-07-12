"""
    boxhandle
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtCore
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

    oldBounds = None

    hiliteFace = True

    def __init__(self):
        """
        A drawable, resizable box that can respond to mouse events. Emits boundsChanged whenever its bounding box
        changes, and emits boundsChangedDone when the mouse button is released.
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
    boundsChangedDone = QtCore.Signal(BoundingBox, bool)

    @property
    def bounds(self):
        return self.boxNode.selectionBox

    @bounds.setter
    def bounds(self, box):
        if box != self.boxNode.selectionBox:
            self.boxNode.selectionBox = box
            self.faceDragNode.selectionBox = box
            self.boundsChanged.emit(box)

    def dragResizePoint(self, ray):
        # returns a point representing the intersection between the mouse ray
        # and an imaginary plane perpendicular to the dragged face

        """

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

    def boxFromDragSelect(self, ray):
        """
        Create a flat selection from dragging the mouse outside the selection.

        :type ray: mcedit2.util.geometry.Ray
        :rtype: BoundingBox
        """
        point = self.dragStartPoint
        face = self.dragStartFace
        size = [1, 1, 1]

        dim = face >> 1
        size[dim] = 0
        s = [0,0,0]

        if face & 1 == 0:
            s[dim] = 1
            point = point + s

        startBox = BoundingBox(point, size)
        endPoint = ray.intersectPlane(dim, point[dim])
        endBox = BoundingBox(endPoint.intfloor(), size)

        return startBox.union(endBox)

    def mousePress(self, event):

        # Find side of existing selection to drag
        # xxxx can't do this with disjoint selections?
        if self.bounds is not None:
            point, face = boxFaceUnderCursor(self.bounds, event.ray)

            if face is not None:
                log.info("Beginning drag resize")
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
                return True
            else:
                # Didn't hit - start new selection
                self.bounds = None

        # Get ready to start new selection
        if self.bounds is None:
            self.dragStartPoint = event.blockPosition
            self.dragStartFace = faces.FaceYIncreasing  # event.blockFace
            return

    def mouseMove(self, event):
        if self.dragStartPoint:
            # Show new box being dragged out
            newBox = self.boxFromDragSelect(event.ray)
            self.bounds = newBox

        if self.bounds is not None:
            if self.dragResizeFace is not None:
                # Hilite face being dragged
                newBox = self.boxFromDragResize(self.oldBounds, event.ray)
                self.faceDragNode.selectionBox = newBox
                self.faceDragNode.visible = True

                # Update selection box to resized size in progress
                newBox = self.boxFromDragResize(self.oldBounds, event.ray)
                self.bounds = newBox

            elif self.hiliteFace:
                # Hilite face cursor is over
                point, face = boxFaceUnderCursor(self.bounds, event.ray)
                if face is not None:
                    self.faceDragNode.visible = True
                    self.faceDragNode.face = face
                    self.faceDragNode.selectionBox = self.bounds
                else:
                    self.faceDragNode.visible = False

    def mouseRelease(self, event):
        if self.dragStartPoint:
            newBox = self.boxFromDragSelect(event.ray)
            self.dragStartPoint = None
            self.bounds = newBox
            self.boundsChangedDone.emit(newBox, True)

        elif self.dragResizeFace is not None:
            self.bounds = self.boxFromDragResize(self.oldBounds, event.ray)
            self.oldBounds = None
            self.dragResizeFace = None
            self.faceDragNode.visible = False
            self.boundsChangedDone.emit(self.bounds, False)
