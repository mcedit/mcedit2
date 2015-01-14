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



def describeKeys(viewAction):
    modifierKeyNames = {
        Qt.Key_Shift: QtGui.qApp.tr("Shift"),
        Qt.Key_Control: QtGui.qApp.tr("Control"),
        Qt.Key_Alt: QtGui.qApp.tr("Alt"),
        Qt.Key_Meta: QtGui.qApp.tr("Meta"),
    }

    s = modifierKeyNames.get(viewAction.key)  # QKeySequence returns weird strings when only a modifier is pressed
    if s is None:
        s = QtGui.QKeySequence(viewAction.key | viewAction.modifiers).toString()
    if viewAction.key == 0:
        s = s[:-2]

    if hasattr(viewAction, 'button'):
        if len(s):
            s += "+"
        s += buttonName(viewAction.button)
    return s

class ButtonModifierInput(QtGui.QPushButton):
    def __init__(self, viewAction, *a, **kw):
        """

        :type viewAction: mcedit2.worldview.worldview.ViewMouseAction
        """
        super(ButtonModifierInput, self).__init__(text=describeKeys(viewAction), *a, **kw)
        self.clicked.connect(self.buttonClicked)
        self.viewAction = viewAction
        self.inputWidget = ModifierInputWidget(self)

    def buttonClicked(self):
        inputWidget = self.inputWidget
        inputWidget.show()

        rect = inputWidget.geometry()
        topRight = self.parent().mapToGlobal(self.geometry().topLeft())
        rect.moveTopRight(topRight)
        inputWidget.setGeometry(rect)

    def updateText(self):
        self.setText(describeKeys(self.viewAction))

    @property
    def key(self):
        return self.viewAction.key

    @key.setter
    def key(self, value):
        self.viewAction.key = value
        self.updateText()

    @property
    def modifiers(self):
        return self.viewAction.modifiers

    @modifiers.setter
    def modifiers(self, value):
        self.viewAction.modifiers = value
        self.updateText()

    @property
    def button(self):
        return self.viewAction.button

    @button.setter
    def button(self, value):
        if hasattr(self.viewAction, 'button'):
            self.viewAction.button = value
            self.updateText()


class ModifierInputWidget(QtGui.QWidget):
    def __init__(self, inputButton, *a, **kw):
        """

        :type inputButton: ButtonModifierInput
        """
        super(ModifierInputWidget, self).__init__(f=Qt.Popup, *a, **kw)
        self.inputLabel = QtGui.QLabel(describeKeys(inputButton))

        if hasattr(inputButton.viewAction, "button"):
            s = "Click a mouse button or press a key, while holding any number of modifier keys (Shift, Ctrl, Alt)"
        else:
            s = "Press a key while holding any number of modifier keys (Shift, Ctrl, Alt)"

        self.helpLabel = QtGui.QLabel(s)
        self.setLayout(Column(self.inputLabel, self.helpLabel))
        self.helpLabel.mousePressEvent = self.mousePressEvent
        self.inputButton = inputButton

    def mousePressEvent(self, mouseEvent):
        """

        :type mouseEvent: QtGui.QMouseEvent
        """
        if not self.rect().contains(mouseEvent.pos()):
            super(ModifierInputWidget, self).mousePressEvent(mouseEvent)
            return

        if not hasattr(self.inputButton.viewAction, "button"):
            return

        self.inputButton.modifiers = mouseEvent.modifiers()
        self.inputButton.button = mouseEvent.button()
        self.inputLabel.setText(describeKeys(self.inputButton.viewAction))

    def keyPressEvent(self, keyEvent):
        """

        :param keyEvent:
        :type keyEvent: QtGui.QKeyEvent
        :return:
        :rtype:
        """
        key = keyEvent.key()
        if key == Qt.Key_Escape:
            self.close()
            return

        modifiers = keyEvent.modifiers()

        log.info("Control change: key %s modifiers %s", hex(key), hex(int(modifiers)))

        self.inputButton.modifiers = modifiers
        self.inputButton.key = key
        self.inputButton.button = Qt.NoButton
        self.inputLabel.setText(describeKeys(self.inputButton.viewAction))


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

        for mouseAction in self.worldView.mouseActions + self.worldView.keyActions:
            if not mouseAction.hidden:
                modInput = ButtonModifierInput(mouseAction, enabled=False)
                self.controlInputs.append(modInput)
                layout.addRow(QtGui.QLabel(mouseAction.labelText), modInput)

        self.hideTime = time.time()

        action = QtGui.QAction("Controls", self)
        action.triggered.connect(self.toggleShowHide)

        self.controlsButton = QtGui.QToolButton()
        self.controlsButton.setDefaultAction(action)

        self.unlockButton = QtGui.QPushButton("Edit Controls", clicked=self.unlockControls)
        self.setLayout(Column(layout, self.unlockButton))

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
