"""
    __init__.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtCore, QtGui
from mcedit2.util.lazyprop import weakrefprop
from mcedit2.util.resources import resourcePath


log = logging.getLogger(__name__)

_registered_tools = []

def RegisterTool(cls):
    """
    Register a tool class. Class must inherit from EditorTool.

    >>> @RegisterTool
    >>> class MyTool(EditorTool):
    >>>     pass

    :param cls:
    :type cls:
    :return:
    :rtype:
    """
    if issubclass(cls, EditorTool):
        _registered_tools.append(cls)
    else:
        raise ValueError("Class %s must inherit from EditorTool" % cls)
    return cls

_scanned_modules = None

def ToolClasses():
    from . import brush
    from . import move
    from . import generate
    from . import edit_chunk
    from . import edit_entity
    from . import select
    from . import flood_fill

    return (select.SelectionTool,
            move.MoveTool,
            brush.BrushTool,
            flood_fill.FloodFillTool,
            generate.GenerateTool,
            edit_chunk.ChunkTool,
            edit_entity.EntityTool,
    )

#     global _scanned_modules
#     if _scanned_modules is None:
#         _scanned_modules = list(ScanToolModules())
#     return iter(_registered_tools)
#
# def ScanToolModules():
#     return ScanModules(__name__, __file__)


class EditorTool(QtCore.QObject):
    name = "Unnamed tool"
    iconName = None
    toolWidget = None
    cursorNode = None
    overlayNode = None
    editorSession = weakrefprop()

    def __init__(self, editorSession, *args, **kwargs):
        """
        Initialize toolWidget here.

        :type editorSession: EditorSession
        """
        super(EditorTool, self).__init__(*args, **kwargs)
        self.editorSession = editorSession

    def mousePress(self, event):
        """
        :type event: QMouseEvent
        event has been augmented with these attributes:

            point, ray, blockPosition, blockFace
        """

    def mouseMove(self, event):
        """
        :type event: QMouseEvent

        event has been augmented
        """

    def mouseDrag(self, event):
        """
        :type event: QMouseEvent

        event has been augmented
        """

    def mouseRelease(self, event):
        """
        :type event: QMouseEvent

        event has been augmented
        """

    def toolActive(self):
        """
        Called when this tool is selected.
        :return:
        :rtype:
        """

    def toolInactive(self):
        """
        Called when a different tool is selected.
        :return:
        :rtype:
        """

    toolPicked = QtCore.Signal(object)

    def pick(self):
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
            )
        action.toolName = name

        return action

