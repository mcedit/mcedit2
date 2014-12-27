"""
    viewcontrols
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from PySide.QtCore import Qt
import time
from mcedit2.widgets.layout import Column

log = logging.getLogger(__name__)

_buttonNames = [
    (Qt.LeftButton, "Left Button"),
    (Qt.RightButton, "Right Button"),
    (Qt.MiddleButton, "Middle Button"),
]


def buttonName(buttons):
    parts = [name for mask, name in _buttonNames if buttons & mask]
    return "+".join(parts)

def modifierText(mouseAction):
    return QtGui.QKeySequence(mouseAction.modifiers).toString() + buttonName(mouseAction.button)

class ButtonModifierInput(QtGui.QPushButton):
    def __init__(self, action, *a, **kw):
        super(ButtonModifierInput, self).__init__(flat=True, text=modifierText(action), *a, **kw)
        self.clicked.connect(self.buttonClicked)
        self.inputWidget = ModifierInputWidget(action)

    def buttonClicked(self):
        self.inputWidget.show()

class ModifierInputWidget(QtGui.QWidget):
    def __init__(self, mouseAction, *a, **kw):
        """

        :type mouseAction: ViewMouseAction
        """
        super(ModifierInputWidget, self).__init__(f=Qt.Popup, *a, **kw)
        self.inputLabel = QtGui.QLabel(modifierText(mouseAction))
        self.helpLabel = QtGui.QLabel("Click mouse button xxor press a keyxx, while holding any number of modifier keys (Shift, Ctrl, Alt)")

        self.setLayout(Column(self.inputLabel, self.helpLabel))
        self.helpLabel.mousePressEvent = self.mousePressEvent
        self.mouseAction = mouseAction

    def mousePressEvent(self, mouseEvent):
        """

        :type mouseEvent: QMouseEvent
        """
        ks = QtGui.QKeySequence(mouseEvent.modifiers())
        s = ks.toString() + buttonName(mouseEvent.button())
        self.inputLabel.setText(s)
        self.mouseAction.modifiers = mouseEvent.modifiers()
        self.mouseAction.button = mouseEvent.button()

    #
    #def keyPressEvent(self, *args, **kwargs):
    #    pass
    #
    #def keyReleaseEvent(self, *args, **kwargs):
    #    pass
    #
    #def mouseReleaseEvent(self, mouseEvent):
    #    pass
    #
    #def __init__(self, mouseAction, *args, **kwargs):
    #    super(ButtonModifierInput, self).__init__(*args, **kwargs)
    #    self.setMaximumWidth(150)
    #    self.mouseAction = mouseAction
    #    self.setText()

class ViewControls(QtGui.QFrame):
    def __init__(self, worldView, *args, **kwargs):
        """


        :type worldView: WorldView
        :param worldView:
        :param args:
        :param kwargs:
        """
        super(ViewControls, self).__init__(f=Qt.Popup, *args, **kwargs)
        self.worldView = worldView
        layout = QtGui.QFormLayout()
        self.controlInputs = []

        for mouseAction in self.worldView.mouseActions:
            if not mouseAction.hidden:
                modInput = ButtonModifierInput(mouseAction, enabled=False)
                self.controlInputs.append(modInput)
                layout.addRow(QtGui.QLabel(mouseAction.labelText), modInput)

        self.hideTime = time.time()

        action = QtGui.QAction("Controls", self)
        action.triggered.connect(self.toggleShowHide)

        self.controlsButton = QtGui.QToolButton()
        self.controlsButton.setDefaultAction(action)

        self.unlockButton = QtGui.QPushButton("Edit", clicked=self.unlockControls)
        layout.addRow(QtGui.QLabel("Edit Controls:"), self.unlockButton)
        self.setLayout(layout)

    def unlockControls(self):
        for ci in self.controlInputs:
            ci.setEnabled(True)
            self.unlockButton.setEnabled(False)

    def lockControls(self):
        for ci in self.controlInputs:
            ci.setEnabled(False)
            self.unlockButton.setEnabled(True)

    def getShowHideButton(self):
        return self.controlsButton

    def hideEvent(self, *a):
        self.hideTime = time.time()
        self.lockControls()

    def toggleShowHide(self):
        if self.isHidden():
            if time.time() - self.hideTime > 0.25:
                self.show()
                rect = self.geometry()
                bottomRight = self.controlsButton.parent().mapToGlobal(self.controlsButton.geometry().bottomRight())
                rect.moveTopRight(bottomRight)
                self.setGeometry(rect)

        else:
            self.hide()
