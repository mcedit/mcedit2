"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging
import os
from PySide import QtGui, QtCore
from mcedit2.editortools.brush import BrushShapeSetting
from mcedit2.editortools.brush.shapes import getShapes
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.util.resources import resourcePath
from mcedit2.widgets import flowlayout

log = logging.getLogger(__name__)


@registerCustomWidget
class ShapeWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(ShapeWidget, self).__init__(*args, **kwargs)
        buttons = self.buttons = []
        layout = flowlayout.FlowLayout()
        actionGroup = QtGui.QActionGroup(self)
        actionGroup.setExclusive(True)
        iconBase = resourcePath("mcedit2/assets/mcedit2/icons")
        actions = {}
        for shape in getShapes():
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
                    self.shapeChanged.emit()
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
            layout.addWidget(button)
            actionGroup.addAction(action)
            actions[shape.ID] = action

        self.setLayout(layout)
        currentID = BrushShapeSetting.value(getShapes()[0].ID)
        shapesByID = {shape.ID:shape for shape in getShapes()}
        actions[currentID].setChecked(True)

        self.currentShape = shapesByID.get(currentID, getShapes()[0])

    shapeChanged = QtCore.Signal()


