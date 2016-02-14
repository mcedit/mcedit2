"""
    viewcontrols
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from PySide.QtCore import Qt
import time
from mcedit2.widgets.layout import Column
from mcedit2.worldview.viewaction import ViewAction

log = logging.getLogger(__name__)



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

        self.inputLabel = QtGui.QLabel(inputButton.viewAction.describeKeys())
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
        self.inputLabel.setText(self.inputButton.viewAction.describeKeys())

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
        self.inputLabel.setText(self.inputButton.viewAction.describeKeys())

    def wheelEvent(self, wheelEvent):
        if not self.inputButton.viewAction.acceptsMouseWheel:
            return

        delta = wheelEvent.delta()
        if delta == 0:
            return
        if delta > 0:
            button = ViewAction.WHEEL_UP
        else:
            button = ViewAction.WHEEL_DOWN

        modifiers = wheelEvent.modifiers()

        log.info("Control change: button %s modifiers %s", button, hex(int(modifiers)))

        self.inputButton.setBinding(button, 0, modifiers)
        self.inputLabel.setText(self.inputButton.viewAction.describeKeys())


class ButtonModifierInput(QtGui.QPushButton):
    def __init__(self, viewAction, *a, **kw):
        """
        Button that displays the current key/mouse binding for a view action. Click the button to change the binding.

        :type viewAction: mcedit2.worldview.viewaction.ViewAction
        """
        super(ButtonModifierInput, self).__init__(text=viewAction.describeKeys(), *a, **kw)
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
        self.setText(self.viewAction.describeKeys())

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
    def __init__(self, worldView, auxWidget=None, *args, **kwargs):
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
        col = [layout, self.unlockButton]
        if auxWidget is not None:
            col.append(auxWidget)

        self.setLayout(Column(*col))
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
