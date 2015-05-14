"""
    plugins
"""
from __future__ import absolute_import, division, print_function
from collections import defaultdict
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

_pluginClassesByModule = defaultdict(list)
_currentPluginModule = None

def loadModule(pluginModule):
    global _currentPluginModule
    if hasattr(pluginModule, "register"):
        _currentPluginModule = pluginModule
        pluginModule.register()
        _currentPluginModule = None

def unloadModule(pluginModule):
    if hasattr(pluginModule, "unregister"):
        pluginModule.unregister()

    classes = _pluginClassesByModule.pop(pluginModule)
    if classes:
        for cls in classes:
            _unregisterClass(cls)

def _registerClass(cls):
    _pluginClassesByModule[_currentPluginModule].append(cls)

def _unregisterClass(cls):
    load_ui.unregisterCustomWidget(cls)
    editortools.unregisterToolClass(cls)
    generate.unregisterGeneratePlugin(cls)
    inspector.unregisterBlockInspectorWidget(cls)
    entities.unregisterTileEntityRefClass(cls)

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
    _registerClass(cls)
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
    _registerClass(cls)
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
    _registerClass(cls)
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
    _registerClass(cls)
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
    _registerClass(cls)
    return entities.registerTileEntityRefClass(ID, cls)
