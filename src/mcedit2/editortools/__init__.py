"""
    __init__.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtCore, QtGui

from mceditlib.util.lazyprop import weakrefprop
from mcedit2.util.resources import resourcePath


log = logging.getLogger(__name__)

_registered_tools = []

def registerToolClass(cls):
    if issubclass(cls, EditorTool):
        _registered_tools.append(cls)
    else:
        raise ValueError("Class %s must inherit from EditorTool" % cls)
    return cls

def unregisterToolClass(cls):
    _registered_tools[:] = [c for c in _registered_tools if c != cls]

_scanned_modules = None

def ToolClasses():
    from . import brush
    from . import move
    from . import generate
    from . import edit_chunk
    from . import select_entity
    from . import select
    from . import flood_fill
    from . import select_block
    from . import clone
    return (select.SelectionTool,
            move.MoveTool,
            clone.CloneTool,
            brush.BrushTool,
            flood_fill.FloodFillTool,
            generate.GenerateTool,
            edit_chunk.ChunkTool,
            select_entity.SelectEntityTool,
            select_block.SelectBlockTool,
    )


class EditorTool(QtCore.QObject):
    name = "Unnamed tool"
    iconName = None
    toolWidget = None
    cursorNode = None
    overlayNode = None
    editorSession = weakrefprop()

    modifiesWorld = False

    def __init__(self, editorSession, *args, **kwargs):
        """
        Initialize toolWidget here.

        Parameters
        ----------

        editorSession: EditorSession
        """
        super(EditorTool, self).__init__(*args, **kwargs)
        self.editorSession = editorSession

    def mousePress(self, event):
        """
        Parameters
        ----------

        event: QMouseEvent
            event has been augmented with these attributes:
            point, ray, blockPosition, blockFace
        """

    def mouseMove(self, event):
        """

        Parameters
        ----------

        event: QMouseEvent
            event has been augmented
        """

    def mouseDrag(self, event):
        """
        Parameters
        ----------

        event: QMouseEvent
            event has been augmented
        """

    def mouseRelease(self, event):
        """
        Parameters
        ----------

        event: QMouseEvent
            event has been augmented
        """

    def toolActive(self):
        """
        Called when this tool is selected.
        """

    def toolInactive(self):
        """
        Called when a different tool is selected.
        """

    toolPicked = QtCore.Signal(object)

    def pick(self):
        if self.editorSession.readonly and self.modifiesWorld:
            return
        self.toolPicked.emit(self.name)

    def pickToolAction(self):
        name = self.name
        iconName = self.iconName
        if iconName:
            iconPath = resourcePath("mcedit2/assets/mcedit2/toolicons/%s.png" % iconName)
            if not os.path.exists(iconPath):
                log.error("Tool icon %s not found", iconPath)
                icon = None
            else:
                icon = QtGui.QIcon(iconPath)
        else:
            icon = None

        action = QtGui.QAction(
            self.tr(name),
            self,
            #shortcut=self.toolShortcut(name),  # xxxx coordinate with view movement keys
            triggered=self.pick,
            checkable=True,
            icon=icon,
            enabled=not(self.editorSession.readonly and self.modifiesWorld)
            )
        action.toolName = name

        return action

