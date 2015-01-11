"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging
import os
from PySide import QtGui, QtCore
from mcedit2.editortools.brush import BrushShapeSetting, Style
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.util.resources import resourcePath
from mcedit2.widgets import flowlayout
from mceditlib import selection

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
        for shape in Shapes.allShapes:
            filename = os.path.join(iconBase, shape.icon)
            assert os.path.exists(filename), "%r does not exist" % filename
            icon = QtGui.QIcon(filename)
            if icon is None:
                raise ValueError("Failed to read shape icon file %s" % filename)
            def _handler(shape):
                def handler():
                    self.currentShape = shape
                    BrushShapeSetting.setValue(shape.ID)
                    self.shapeChanged.emit()
                return handler
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
        currentID = BrushShapeSetting.value(Shapes.allShapes[0].ID)
        shapesByID = {shape.ID:shape for shape in Shapes.allShapes}
        actions[currentID].setChecked(True)

        self.currentShape = shapesByID.get(currentID, Shapes.allShapes[0])

    shapeChanged = QtCore.Signal()


class Round(Style):
    ID = "Round"
    icon = "shapes/round.png"
    shapeFunc = staticmethod(selection.SphereShape)


class Square(Style):
    ID = "Square"
    icon = "shapes/square.png"
    shapeFunc = staticmethod(selection.BoxShape)


class Diamond(Style):
    ID = "Diamond"
    icon = "shapes/diamond.png"
    shapeFunc = staticmethod(selection.DiamondShape)


class Shapes(object):
    # load from plugins here, rename to selection shapes?
    allShapes = (Square(), Round(), Diamond())
