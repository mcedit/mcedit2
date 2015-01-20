"""
    viewaction
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide.QtCore import Qt
from mcedit2.util.settings import Settings

log = logging.getLogger(__name__)

class ViewAction(object):
    button = Qt.NoButton
    modifiers = Qt.NoModifier
    key = 0
    labelText = "Unknown Action"
    hidden = False  # Hide from configuration
    settingsKey = NotImplemented
    acceptsMouseWheel = False

    def __init__(self):
        """
        An action that can be bound to a keypress or mouse button click, drag, or movement with the bound key or button held.

        """
        if self.settingsKey is not None:
            settings = Settings()
            prefix = "keybindings/"
            self.modifiers = int(settings.value(prefix + self.settingsKey + "/modifiers", self.modifiers))
            self.button = int(settings.value(prefix + self.settingsKey + "/button", self.button))
            self.key = int(settings.value(prefix + self.settingsKey + "/key", self.key))

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

        return self.key == key and (self.modifiers & modifiers or self.modifiers == modifiers)

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


class UseToolMouseAction(ViewAction):
    button = Qt.LeftButton
    labelText = "Use Tool (Don't change!)"
    hidden = True
    settingsKey = None

    def __init__(self, editor):
        super(UseToolMouseAction, self).__init__()
        self.editor = editor

    def mousePressEvent(self, event):
        self.editor.viewMousePress(event)
        event.view.update()

    def mouseMoveEvent(self, event):
        self.editor.viewMouseDrag(event)
        event.view.update()

    def mouseReleaseEvent(self, event):
        self.editor.viewMouseRelease(event)
        event.view.update()


class TrackingMouseAction(ViewAction):
    button = Qt.NoButton
    hidden = True

    labelText = "Mouse Tracking (Don't change!)"
    settingsKey = None

    def __init__(self, editor):
        super(TrackingMouseAction, self).__init__()
        self.editor = editor

    def mouseMoveEvent(self, event):
        self.editor.viewMouseMove(event)


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


class ZoomWheelAction(ViewAction):
    _zooms = None
    labelText = "Zoom View"
    maxScale = 16.
    minScale = 1. / 64
    settingsKey = None

    @property
    def zooms(self):
        if self._zooms:
            return self._zooms
        zooms = []
        _i = self.minScale
        while _i < self.maxScale:
            zooms.append(_i)
            _i *= 2.0

        self._zooms = zooms
        return zooms

    def wheelEvent(self, event):
        d = event.delta()
        mousePos = (event.x(), event.y())

        if d < 0:
            i = self.zooms.index(event.view.scale)
            if i < len(self.zooms) - 1:
                self.zoom(event.view, self.zooms[i + 1], mousePos)
        elif d > 0:
            i = self.zooms.index(event.view.scale)
            if i > 0:
                self.zoom(event.view, self.zooms[i - 1], mousePos)

    def zoom(self, view, scale, (mx, my)):

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
