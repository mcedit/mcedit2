"""
    plugins
"""
from __future__ import absolute_import, division, print_function

import imp
import itertools
import logging
import os
from collections import defaultdict

from mcedit2 import editortools
from mcedit2.editortools import generate
from mcedit2.plugins import command
from mcedit2.util import load_ui
from mcedit2.util.settings import Settings
from mcedit2.widgets import inspector
from mceditlib.anvil import entities

log = logging.getLogger(__name__)

import sys
sys.dont_write_bytecode = True

settings = Settings().getNamespace("plugins")

enabledPluginsSetting = settings.getOption("enabled_plugins", "json", {})
autoReloadSetting = settings.getOption("auto_reload", bool, True)

# *** plugins dialog will need to:
# v get a list of (plugin display name, plugin reference, isEnabled) tuples for loaded and
#       unloaded plugins.
# v enable or disable a plugin using its reference
# - reload a plugin
# - find out if a plugin was removed from the folder or failed to compile or run
# - install a new plugin using a file chooser
# - open the plugins folder(s) in Finder/Explorer

# *** on startup:
# v scan all plugins dirs for plugins
# - check if a plugin is enabled (without executing it?)
# - load plugins set to "enabled" in settings

# *** on app foreground:
# - rescan all plugins dirs
# - show new plugins to user, ask whether to load them
# - when in dev mode (??)
#   - check mod times of all plugin files under each PluginRef
#   - if auto-reload is on, reload plugins
#   - if auto-reload is off, ??? prompt to enable autoreload?


# --- Plugin refs ---

class PluginRef(object):
    _displayName = None

    def __init__(self, filename, pluginsDir):
        self.filename = filename
        self.pluginsDir = pluginsDir
        self.fullpath = None  # Set after findModule is called
        self.pluginModule = None  # None indicates the plugin is not loaded

        self.loadError = None
        self.unloadError = None

        self.timestamps = {}

    def checkTimestamps(self):
        """
        Record the modification time for this plugin's file and return True if it differs
        from the previously recorded time.

        If self.filename specifies a directory, walks the directory tree and records the mod
        times of all files and directories found.
        :return:
        """
        timestamps = {}
        filename = os.path.join(self.pluginsDir, self.filename)
        if os.path.isdir(filename):
            for dirname, subdirs, files in os.walk(filename):
                for child in itertools.chain(subdirs, files):
                    pathname = os.path.join(dirname, child)
                    modtime = os.stat(pathname).st_mtime
                    timestamps[pathname] = modtime

        else:
            modtime = os.stat(filename).st_mtime
            timestamps[filename] = modtime

        changed = timestamps != self.timestamps
        self.timestamps = timestamps
        return changed

    def findModule(self):
        """
        Returns (file, pathname, description).

        May raise ImportError, EnvironmentError, maybe others?

        If it is not none, caller is responsible for closing file. (see `imp.find_module`)
        """
        basename, ext = os.path.splitext(self.filename)
        return imp.find_module(basename, [self.pluginsDir])

    def load(self):
        if self.pluginModule:
            return True

        basename, ext = os.path.splitext(self.filename)
        io = None
        try:
            io, pathname, description = self.findModule()
            self.fullpath = pathname
            log.info("Trying to load plugin from %s", self.filename)
            global _currentPluginPathname
            _currentPluginPathname = pathname

            self.pluginModule = imp.load_module(basename, io, pathname, description)
            _loadedModules[self.fullpath] = self.pluginModule
            self.pluginModule.__FOUND_FILENAME__ = self.fullpath

            _currentPluginPathname = None

            # Plugin registration is deferred until the module is fully loaded.
            for registry in _registries:
                registry.commitRegistrations()

            if hasattr(self.pluginModule, 'displayName'):
                self._displayName = self.pluginModule.displayName

            log.info("Loaded %s (%s)", self.filename, self.displayName)
        except Exception as e:
            self.loadError = sys.exc_info()
            log.exception("Error while loading plugin from %s: %r", self.filename, e)
            return False
        else:
            self.loadError = None
        finally:
            if io:
                io.close()

        return True

    def unload(self):
        if self.pluginModule is None:
            return True
        module = self.pluginModule

        try:
            if hasattr(module, "unregister"):
                module.unregister()

        except Exception as e:
            self.unloadError = sys.exc_info()
            log.exception("Error while unloading plugin from %s: %r", self.filename, e)
            return False
        else:
            self.unloadError = None
        finally:
            log.info("Unloading plugin %s", self.displayName)
            self.pluginModule = None
            deadKeys = []
            for k, v in sys.modules.iteritems():
                if v is module:
                    deadKeys.append(k)

            assert len(deadKeys), "Plugin %s not in sys.modules (uh-oh)" % (self.displayName,)
            for k in deadKeys:
                sys.modules.pop(k)
                log.info("Removed module %s from sys.modules", k)

            classes = _pluginClassesByPathname.pop(self.fullpath)
            if classes:
                for cls in classes:
                    log.info("Unregistered %s", cls)
                    unregisterClass(cls)

            _loadedModules.pop(module.__FOUND_FILENAME__)
            self.fullpath = None

        return True

    @property
    def isLoaded(self):
        return self.pluginModule is not None

    @property
    def displayName(self):
        if self._displayName:
            return self._displayName

        return os.path.splitext(os.path.basename(self.filename))[0]

    def exists(self):
        return os.path.exists(self.fullpath)

    @property
    def enabled(self):
        enabledPlugins = enabledPluginsSetting.value()
        return enabledPlugins.get(self.filename, True)

    @enabled.setter
    def enabled(self, value):
        value = bool(value)
        enabledPlugins = enabledPluginsSetting.value()
        enabledPlugins[self.filename] = value
        enabledPluginsSetting.setValue(enabledPlugins)

# --- Plugin finding ---

_pluginRefs = {}


def getAllPlugins():
    """
    Return all known plugins as a list of `PluginRef`s

    :return: list[PluginRef]
    :rtype:
    """
    return list(_pluginRefs.values())


def findNewPluginsInDir(pluginsDir):
    if not os.path.isdir(pluginsDir):
        log.warn("Plugins dir %s not found", pluginsDir)
        return

    log.info("Loading plugins from %s", pluginsDir)

    for filename in os.listdir(pluginsDir):
        if filename not in _pluginRefs:
            ref = detectPlugin(filename, pluginsDir)
            if ref:
                ref.checkTimestamps()
                _pluginRefs[filename] = ref


def detectPlugin(filename, pluginsDir):
    io = None
    basename, ext = os.path.splitext(filename)
    if ext in (".pyc", ".pyo"):
        return None

    ref = PluginRef(filename, pluginsDir)
    try:
        io, pathname, description = ref.findModule()
    except Exception as e:
        log.exception("Could not detect %s as a plugin or module: %s", filename, e)
        return None
    else:
        return ref
    finally:
        if io:
            io.close()


# --- Plugin registration ---

_loadedModules = {}
_pluginClassesByPathname = defaultdict(list)
_currentPluginPathname = None

_registries = [
    command.CommandPlugins,
    generate.GeneratePlugins
]

def registerClass(cls):
    _pluginClassesByPathname[_currentPluginPathname].append(cls)
    log.info("Registered class %s of plugin %s", cls, _currentPluginPathname)


def unregisterClass(cls):
    load_ui.unregisterCustomWidget(cls)
    editortools.unregisterToolClass(cls)
    inspector.unregisterBlockInspectorWidget(cls)
    entities.unregisterTileEntityRefClass(cls)

    generate.GeneratePlugins.unregisterClass(cls)
    command.CommandPlugins.unregisterClass(cls)

# --- Registration functions ---

def registerPluginCommand(cls):
    """
    Register a command that can be invoked from the Plugins menu.

    >>> from mcedit2.plugins.command import CommandPlugin
    >>> @registerPluginCommand
    >>> class MyCommand(CommandPlugin)
    >>>     pass

    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    registerClass(cls)
    return command.CommandPlugins.registerClass(cls)


def registerCustomWidget(cls):
    """
    Register a custom QWidget class with the .ui file loader. This allows custom QWidget
    classes to be used in .ui files.

    >>> from PySide import QtGui
    >>> @registerCustomWidget
    >>> class MyWidget(QtGui.QWidget):
    >>>     pass

    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    registerClass(cls)
    return load_ui.registerCustomWidget(cls)

def registerToolClass(cls):
    """
    Register a tool class. Class must inherit from EditorTool.

    >>> from mcedit2.editortools import EditorTool
    >>> @registerToolClass
    >>> class MyTool(EditorTool):
    >>>     pass


    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    registerClass(cls)
    return editortools.registerToolClass(cls)

def registerGeneratePlugin(cls):
    """
    Register a plugin for the Generate Tool. Class must inherit from GeneratePlugin.

    >>> from mcedit2.editortools.generate import GeneratePlugin
    >>> @registerGeneratePlugin
    >>> class MyGeneratePlugin(GeneratePlugin):
    >>>     pass


    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    registerClass(cls)
    return generate.GeneratePlugins.registerClass(cls)

def registerBlockInspectorWidget(cls):
    """
    Register a widget with the Block Inspector for editing a TileEntity

    The class must have a `tileEntityID` attribute.

    >>> from PySide import QtGui
    >>> class MyBarrelInspector(QtGui.QWidget):
    >>>     tileEntityID = "MyBarrel"
    >>>
    >>> registerBlockInspectorWidget(MyBarrelInspector)


    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    registerClass(cls)
    return inspector.registerBlockInspectorWidget(cls)

def registerTileEntityRefClass(ID, cls):
    """
    Register a TileEntityRef class with the world loader to create when loading a TileEntity
    with the given ID.

    xxx specify world format here, too.

    >>> from mceditlib.anvil.entities import PCTileEntityRefBase
    >>> class MyBarrelRef(PCTileEntityRefBase):
    >>>     pass
    >>> registerTileEntityRefClass("MyBarrel", MyBarrelRef)


    Parameters
    ----------
    cls : Class

    Returns
    -------
    cls : Class
    """
    # xxx this is anvil.entities - delegate to correct world format
    registerClass(cls)
    return entities.registerTileEntityRefClass(ID, cls)

# Convenience imports for plugin modules

from .command import CommandPlugin, SimpleCommandPlugin
