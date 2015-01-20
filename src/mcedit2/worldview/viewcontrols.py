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
        "WHEEL_UP": QtGui.qApp.tr("Mousewheel Up"),
        "WHEEL_DOWN": QtGui.qApp.tr("Mousewheel Down"),

    }

    s = modifierKeyNames.get(viewAction.key)  # QKeySequence returns weird strings when only a modifier is pressed
    if s is None:
        try:
            s = QtGui.QKeySequence(viewAction.key | viewAction.modifiers).toString()
        except TypeError:
            log.error("KEY: %r MOD: %r", viewAction.key, viewAction.modifiers)
            raise
    if viewAction.key == 0:
        s = s[:-2]

    if viewAction.button != Qt.NoButton:
        if len(s):
            s += "+"
        s += buttonName(viewAction.button)
    return s


class ModifierInputWidget(QtGui.QWidget):
    def __init__(self, inputButton, *a, **kw):
        """
        Popup widget to change the binding for a view action.

        :type inputButton: ButtonModifierInput
        """
        super(ModifierInputWidget, self).__init__(f=Qt.Popup, *a, **kw)
        self.setMaximumWidth(150)

        frame = QtGui.QFrame()
        frame.setFrameStyle(QtGui.QFrame.Box)

        self.inputLabel = QtGui.QLabel(describeKeys(inputButton))
        self.inputLabel.setAlignment(Qt.AlignCenter)
        font = self.inputLabel.font()
        font.setPointSize(font.pointSize() * 1.5)
        font.setBold(True)
        self.inputLabel.setFont(font)
        if hasattr(inputButton.viewAction, "button"):
            s = "Click a mouse button or press a key, while holding any number of modifier keys (Shift, Ctrl, Alt)"
        else:
            s = "Press a key while holding any number of modifier keys (Shift, Ctrl, Alt)"

        self.helpLabel = QtGui.QLabel(s)
        frame.setLayout(Column(self.inputLabel, self.helpLabel))
        self.setLayout(Column(frame, margin=0))
        self.helpLabel.mousePressEvent = self.mousePressEvent
        self.inputButton = inputButton

    def mousePressEvent(self, mouseEvent):
        """

        :type mouseEvent: QtGui.QMouseEvent
        """
        if not self.rect().contains(mouseEvent.pos()):
            super(ModifierInputWidget, self).mousePressEvent(mouseEvent)
            return

        if mouseEvent.button() == Qt.LeftButton:
            return  # Forbid binding left button

        self.inputButton.setBinding(mouseEvent.button(), 0, mouseEvent.modifiers())
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

        log.info("Control change: key %s(%s) modifiers %s(%s)", key, hex(key), modifiers, hex(int(modifiers)))

        self.inputButton.setBinding(Qt.NoButton, key, modifiers)
        self.inputLabel.setText(describeKeys(self.inputButton.viewAction))

    def wheelEvent(self, wheelEvent):
        if not self.inputButton.viewAction.acceptsMouseWheel:
            return

        delta = wheelEvent.delta()
        if delta == 0:
            return
        if delta > 0:
            key = "WHEEL_UP"
        else:
            key = "WHEEL_DOWN"

        modifiers = wheelEvent.modifiers()

        log.info("Control change: key %s modifiers %s", key, hex(int(modifiers)))

        self.inputButton.setBinding(Qt.NoButton, key, modifiers)
        self.inputLabel.setText(describeKeys(self.inputButton))


class ButtonModifierInput(QtGui.QPushButton):
    def __init__(self, viewAction, *a, **kw):
        """
        Button that displays the current key/mouse binding for a view action. Click the button to change the binding.

        :type viewAction: mcedit2.worldview.viewaction.ViewAction
        """
        super(ButtonModifierInput, self).__init__(text=describeKeys(viewAction), *a, **kw)
        self.setStyleSheet("""
        :disabled {
            color: #000000;
        }

        :enabled {
            background-color: #DDDDFF;
        """)
        self.clicked.connect(self.buttonClicked)
        self.viewAction = viewAction
        self.inputWidget = ModifierInputWidget(self)

    def buttonClicked(self):
        inputWidget = self.inputWidget
        inputWidget.show()
        inputWidget.setFocus()

        rect = inputWidget.geometry()
        topRight = self.parent().mapToGlobal(self.geometry().bottomRight())
        rect.moveTopRight(topRight)
        inputWidget.setGeometry(rect)

    def updateText(self):
        self.setText(describeKeys(self.viewAction))

    @property
    def key(self):
        return self.viewAction.key

    @property
    def modifiers(self):
        return self.viewAction.modifiers

    @property
    def button(self):
        return self.viewAction.button

    def setBinding(self, button, key, modifiers):
        self.viewAction.setBinding(button, key, modifiers)
        self.updateText()


class ViewControls(QtGui.QFrame):
    def __init__(self, worldView, *args, **kwargs):
        """
        Popup window for quickly reviewing and assigning movement controls for a world view.

        :type worldView: WorldView
        :param worldView:
        :param args:
        :param kwargs:
        """
        super(ViewControls, self).__init__(f=Qt.Popup, *args, **kwargs)
        self.worldView = worldView
        layout = QtGui.QFormLayout()
        self.controlInputs = []

        for action in self.worldView.viewActions:
            if not action.hidden:
                modInput = ButtonModifierInput(action, enabled=False)
                self.controlInputs.append(modInput)
                layout.addRow(QtGui.QLabel(action.labelText), modInput)

        self.hideTime = time.time()

        action = QtGui.QAction(self.tr("Controls"), self)
        action.triggered.connect(self.toggleShowHide)

        self.controlsButton = QtGui.QToolButton()
        self.controlsButton.setDefaultAction(action)

        self.unlockButton = QtGui.QPushButton(self.tr("Edit Controls"), clicked=self.toggleUnlockControls)
        self.setLayout(Column(layout, self.unlockButton))
        self.unlocked = False

    def toggleUnlockControls(self):
        self.lockUnlockControls(not self.unlocked)

    def lockUnlockControls(self, unlocked):
        self.unlocked = unlocked
        for ci in self.controlInputs:
            ci.setEnabled(unlocked)
            self.unlockButton.setText(self.tr("Done Editing") if unlocked else self.tr("Edit Controls"))

    def getShowHideButton(self):
        return self.controlsButton

    def hideEvent(self, *a):
        self.hideTime = time.time()
        self.lockUnlockControls(False)

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
