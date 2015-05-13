"""
    plugins
"""
from __future__ import absolute_import, division, print_function
import logging
from mcedit2 import editortools
from mcedit2.editortools import generate
from mcedit2.util import load_ui
from mcedit2.widgets import inspector
from mceditlib.anvil import entities

log = logging.getLogger(__name__)

# TODO: plugin unregistration
# Either add a register/unregister method to plugin modules, or
# keep track of which plugin is doing the registering and associate
# it with its classes so MCEdit can unregister them automatically
# Allowing plugin classes to be unregistered allows reloading plugins and disabling plugins after load times.

def registerCustomWidget(cls):
    """
    Register a custom QWidget class with the .ui file loader. This allows custom QWidget
    classes to be used in .ui files.

    >>> from PySide import QtGui
    >>> @registerCustomWidget
    >>> class MyWidget(QtGui.QWidget):
    >>>     pass

    :param cls:
    :type cls: class
    :return:
    :rtype: class
    """
    return load_ui.registerCustomWidget(cls)

def registerToolClass(cls):
    """
    Register a tool class. Class must inherit from EditorTool.

    >>> from mcedit2.editortools import EditorTool
    >>> @registerToolClass
    >>> class MyTool(EditorTool):
    >>>     pass

    :param cls:
    :type cls: class
    :return:
    :rtype: class
    """
    return editortools.registerToolClass(cls)

def registerGeneratePlugin(cls):
    """
    Register a plugin for the Generate Tool. Class must inherit from GeneratePlugin.

    >>> from mcedit2.editortools.generate import GeneratePlugin
    >>> @registerGeneratePlugin
    >>> class MyGeneratePlugin(GeneratePlugin):
    >>>     pass

    :param cls:
    :type cls:
    :return:
    :rtype:
    """
    return generate.registerGeneratePlugin(cls)

def registerBlockInspectorWidget(ID, cls):
    """
    Register a widget with the Block Inspector to use when inspecting TileEntities
    that have the given ID.

    xxx make ID an attribute of cls?

    >>> from PySide import QtGui
    >>> class MyBarrelInspector(QtGui.QWidget):
    >>>     pass
    >>> registerBlockInspectorWidget("MyBarrel", MyBarrelInspector)

    :param cls:
    :type cls:
    :return:
    :rtype:
    """
    return inspector.registerBlockInspectorWidget(ID, cls)

def registerTileEntityRefClass(ID, cls):
    """
    Register a TileEntityRef class with the world loader to create when loading a TileEntity
    with the given ID.

    xxx specify world format here, too.

    >>> from mceditlib.anvil.entities import PCTileEntityRefBase
    >>> class MyBarrelRef(PCTileEntityRefBase):
    >>>     pass
    >>> registerTileEntityRefClass("MyBarrel", MyBarrelRef)

    :param cls:
    :type cls:
    :return:
    :rtype:
    """
    # xxx this is anvil.entities - delegate to correct world format
    return entities.registerTileEntityRefClass(ID, cls)
