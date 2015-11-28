"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function

import logging
import os

from PySide import QtGui, QtCore

from mcedit2.editortools.tool_settings import BrushShapeSetting
from mcedit2.util.resources import resourcePath
from mcedit2.widgets import flowlayout
from mcedit2.widgets.layout import Column

log = logging.getLogger(__name__)


class ShapeWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        addShapes = kwargs.pop('addShapes', None)
        super(ShapeWidget, self).__init__(*args, **kwargs)
        buttons = self.buttons = []
        self.groupBox = QtGui.QGroupBox("Shape:")

        flowLayout = flowlayout.FlowLayout()
        actionGroup = QtGui.QActionGroup(self)
        actionGroup.setExclusive(True)
        iconBase = resourcePath("mcedit2/assets/mcedit2/icons")
        actions = {}

        from mcedit2.editortools.brush.shapes import getShapes  # xxx circular import
        shapes = list(getShapes())

        if addShapes:
            shapes.extend(addShapes)

        for shape in shapes:
            if shape.icon is not None:
                filename = os.path.join(iconBase, shape.icon)
                assert os.path.exists(filename), "%r does not exist" % filename
                icon = QtGui.QIcon(filename)
                if icon is None:
                    log.warn("Failed to read shape icon file %s" % filename)
            else:
                icon = None

            def _handler(shape):
                def handler():
                    self.currentShape = shape
                    BrushShapeSetting.setValue(shape.ID)
                    self.shapeChanged.emit(shape)
                return handler
            if icon is None:
                action = QtGui.QAction(shape.ID, self, triggered=_handler(shape))
            else:
                action = QtGui.QAction(icon, shape.ID, self, triggered=_handler(shape))
            button = QtGui.QToolButton()
            action.setCheckable(True)
            button.setDefaultAction(action)
            button.setIconSize(QtCore.QSize(32, 32))
            buttons.append(button)
            flowLayout.addWidget(button)
            actionGroup.addAction(action)
            actions[shape.ID] = action
            shape.optionsChanged.connect(self.shapeOptionsChanged.emit)

        self.optionsHolder = QtGui.QStackedWidget()
        layout = Column(flowLayout, (self.optionsHolder, 1))
        self.groupBox.setLayout(layout)
        self.setLayout(Column(self.groupBox, margin=0))

        currentID = BrushShapeSetting.value(shapes[0].ID)
        shapesByID = {shape.ID: shape for shape in shapes}
        if currentID not in actions:
            currentID = shapes[0].ID
        actions[currentID].setChecked(True)

        self.currentShape = shapesByID.get(currentID, shapes[0])

        self.shapeChanged.connect(self.shapeDidChange)
        self.shapeDidChange(self.currentShape)

    shapeChanged = QtCore.Signal(object)
    shapeOptionsChanged = QtCore.Signal()

    def groupBoxTitle(self, shape):
        return self.tr("Shape: ") + shape.displayName

    def shapeDidChange(self, newShape):
        self.groupBox.setTitle(self.groupBoxTitle(newShape))

        while self.optionsHolder.count():
            self.optionsHolder.removeWidget(self.optionsHolder.widget(0))

        widget = newShape.getOptionsWidget()
        if widget:
            self.optionsHolder.addWidget(widget)



