"""
    viewaction
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mceditlib.util.lazyprop import weakrefprop
from mcedit2.util.settings import Settings


log = logging.getLogger(__name__)


class ViewAction(QtCore.QObject):
    button = Qt.NoButton
    modifiers = Qt.NoModifier
    key = 0
    labelText = "Unknown Action"
    hidden = False  # Hide from configuration
    settingsKey = NotImplemented
    acceptsMouseWheel = False

    WHEEL_UP = 0x100
    WHEEL_DOWN = 0x200

    _buttonNames = None

    def __init__(self):
        """
        An action that can be bound to a keypress or mouse button click, drag, or
        movement with the bound key or button held.

        """
        super(ViewAction, self).__init__()

        if self.settingsKey is not None:
            settings = Settings()
            prefix = "keybindings/"
            try:
                modifiers = int(settings.value(prefix + self.settingsKey + "/modifiers", self.modifiers))
                button = int(settings.value(prefix + self.settingsKey + "/button", self.button))
                key = int(settings.value(prefix + self.settingsKey + "/key", self.key))
            except Exception as e:
                log.error("Error while reading key binding:")
            else:
                self.modifiers = modifiers
                self.button = button
                self.key = key

    def __repr__(self):
        return "%s(button=%s, key=%s, modifiers=%s)" % (self.__class__.__name__, self.button, self.key, self.modifiers)

    def setBinding(self, button, key, modifiers):
        self.button = button
        self.key = key
        self.modifiers = modifiers
        if self.settingsKey is not None:
            settings = Settings()
            prefix = "keybindings/"
            settings.setValue(prefix + self.settingsKey + "/button", self.button)
            settings.setValue(prefix + self.settingsKey + "/key", self.key)
            settings.setValue(prefix + self.settingsKey + "/modifiers", int(self.modifiers))

    def matchKeyEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            modifiers = self.modifiers  # pressing modifier key by itself has modifiers set, but releasing modifiers does not

        matched = self.key == key

        if event.type == QtCore.QEvent.KeyPress:
            # Only match modifiers on key press, ignore modifiers on release to handle
            # input sequences like: S down, Shift down, S up, Shift up
            matched &= (self.modifiers == modifiers)
        return matched
    
    def matchModifiers(self, event):
        return (self.modifiers is None or
                self.modifiers == event.modifiers())
        
    def mouseMoveEvent(self, event):
        """
        Called when the mouse moves while the bound keys or buttons are pressed.

        :type event: QtGui.QMouseEvent
        """

    def mousePressEvent(self, event):
        """
        Called when the bound mouse button is pressed. By default, calls buttonPressEvent.

        :type event: QtGui.QMouseEvent
        """
        self.buttonPressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Called when the bound mouse button is released. By default, calls buttonReleaseEvent

        :type event: QtGui.QMouseEvent
        """
        self.buttonReleaseEvent(event)

    def keyPressEvent(self, event):
        """
        Called when the bound key is pressed. By default, calls buttonPressEvent.

        :type event: QtGui.QKeyEvent
        """
        self.buttonPressEvent(event)

    def keyReleaseEvent(self, event):
        """
        Called when the bound key is released. By default, calls buttonReleaseEvent

        :type event: QtGui.QKeyEvent
        """
        self.buttonReleaseEvent(event)

    def buttonPressEvent(self, event):
        """
        Called by mousePressEvent and keyPressEvent.

        Implement this to handle button-press events if it doesn't matter whether the action is bound to a key or
        mouse button.

        :type event: QtGui.QEvent
        """

    def buttonReleaseEvent(self, event):
        """
        Called by mouseReleaseEvent and keyReleaseEvent.

        Implement this to handle button-release events if it doesn't matter whether the action is bound to a key or
        mouse button.

        :type event: QtGui.QEvent
        """

    def buttonName(self, buttons):
        if ViewAction._buttonNames is None:
            ViewAction._buttonNames = [
                (Qt.LeftButton, self.tr("Left Button")),
                (Qt.RightButton, self.tr("Right Button")),
                (Qt.MiddleButton, self.tr("Middle Button")),
                (ViewAction.WHEEL_UP, self.tr("Mousewheel Up")),
                (ViewAction.WHEEL_DOWN, self.tr("Mousewheel Down")),
            ]
        parts = [name for mask, name in self._buttonNames if buttons & mask]
        return "+".join(parts)

    def describeKeys(self):
        modifierKeyNames = {
            Qt.Key_Shift: self.tr("Shift"),
            Qt.Key_Control: self.tr("Control"),
            Qt.Key_Alt: self.tr("Alt"),
            Qt.Key_Meta: self.tr("Meta"),
        }

        s = modifierKeyNames.get(self.key)  # QKeySequence returns weird strings when only a modifier is pressed
        if s is None:
            try:
                s = QtGui.QKeySequence(self.key | self.modifiers).toString()
            except TypeError:
                log.error("KEY: %r MOD: %r", self.key, self.modifiers)
                raise
        if self.key == 0:
            s = s[:-2]

        if self.button != Qt.NoButton:
            if len(s):
                s += "+"
            s += self.buttonName(self.button)
        return s


class UseToolMouseAction(ViewAction):
    button = Qt.LeftButton
    labelText = "Use Tool (Don't change!)"
    hidden = True
    settingsKey = None
    modifiers = None  # really?

    editorTab = weakrefprop()

    def __init__(self, editorTab):
        super(UseToolMouseAction, self).__init__()
        self.editorTab = editorTab

    def mousePressEvent(self, event):
        self.editorTab.editorSession.viewMousePress(event)
        event.view.update()

    def mouseMoveEvent(self, event):
        self.editorTab.editorSession.viewMouseDrag(event)
        event.view.update()

    def mouseReleaseEvent(self, event):
        self.editorTab.editorSession.viewMouseRelease(event)
        event.view.update()


class TrackingMouseAction(ViewAction):
    button = Qt.NoButton
    hidden = True
    modifiers = None
    labelText = "Mouse Tracking (Don't change!)"
    settingsKey = None

    editorTab = weakrefprop()

    def __init__(self, editorTab):
        super(TrackingMouseAction, self).__init__()
        self.editorTab = editorTab

    def mouseMoveEvent(self, event):
        self.editorTab.editorSession.viewMouseMove(event)


class MoveViewMouseAction(ViewAction):
    button = Qt.RightButton
    labelText = "Pan View"
    settingsKey = "worldview/general/holdToMove"

    def buttonPressEvent(self, event):
        x, y = event.x(), event.y()
        self.dragStart = event.view.unprojectAtHeight(x, y, 0)
        self.startOffset = event.view.centerPoint
        log.debug("Drag start %s", self.dragStart)

        event.view.update()

    def mouseMoveEvent(self, event):
        x = event.x()
        y = event.y()
        log.debug("mouseMoveEvent %s", (x, y))

        if self.dragStart:
            d = event.view.unprojectAtHeight(x, y, 0) - self.dragStart
            event.view.centerPoint -= d
            log.debug("Drag continue delta %s", d)

            event.view.update()

    def buttonReleaseEvent(self, event):
        x, y = event.x(), event.y()
        self.dragStart = None
        log.debug("Drag end")

        event.view.update()


def ZoomWheelActions():
    maxScale = 16.
    minScale = 1. / 64
    
    zooms = []
    _i = minScale
    while _i < maxScale:
        zooms.append(_i)
        _i *= 2.0
    
    def zoom(view, scale, (mx, my)):

        # Get mouse position in world coordinates
        worldPos = view.unprojectAtHeight(mx, my, 0)

        if scale != view.scale:
            view.scale = scale

            # Get the new position under the mouse, find its distance from the old position,
            # and shift the centerPoint by that amount.

            newWorldPos = view.unprojectAtHeight(mx, my, 0)
            delta = newWorldPos - worldPos
            view.centerPoint = view.centerPoint - delta

            log.debug("zoom offset %s, pos %s, delta %s, scale %s", view.centerPoint, (mx, my), delta, view.scale)
    
    class ZoomInAction(ViewAction):
        settingsKey = "worldview.general.zoom_in"
        button = ViewAction.WHEEL_UP
        acceptsMouseWheel = True
        labelText = "Zoom In"
        
        def buttonPressEvent(self, event):
            log.debug(self.labelText)
            mousePos = (event.x(), event.y())

            i = zooms.index(event.view.scale)
            if i > 0:
                zoom(event.view, zooms[i - 1], mousePos)

    class ZoomOutAction(ViewAction):
        settingsKey = "worldview.general.zoom_out"
        button = ViewAction.WHEEL_DOWN
        acceptsMouseWheel = True
        labelText = "Zoom Out"
        
        def buttonPressEvent(self, event):
            log.debug(self.labelText)
            mousePos = (event.x(), event.y())
    
            i = zooms.index(event.view.scale)
            if i < len(zooms) - 1:
                zoom(event.view, zooms[i + 1], mousePos)

    return [ZoomInAction(), ZoomOutAction()]