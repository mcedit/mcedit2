"""
    command
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from collections import defaultdict

from PySide import QtCore, QtGui

log = logging.getLogger(__name__)


class PluginCommand(QtCore.QObject):
    def __init__(self, editorSession):
        """
        A new PluginCommand instance is created for each world opened in an editor
        session. During initialization, the instance should set up any UI widgets it
        needs and add a menu item to the Plugins menu by calling `self.addMenuItem`. The
        instance may inspect the world opened by the editor session and opt not to
        add any menu item for any reason, e.g. if the world format isn't supported
        by this plugin.

        Remember to call `super(MyCommandClass, self).__init__(editorSession)`

        Parameters
        ----------
        editorSession : EditorSession
        """
        super(PluginCommand, self).__init__()
        self.editorSession = editorSession

    def addMenuItem(self, text, func, submenu=None):
        """
        Adds an item to the Plugins menu with the given text. When the user chooses this
        menu item, the given function will be called. The text should be marked
        for translation using `self.tr()`.

        If submenu is given, the menu item will be added to a submenu with the given text.
        submenu should also be marked for translation.

        Returns the QAction that implements the menu item. This allows the plugin instance
        to enable/disable the menu item at any time, e.g. in response to changes in the
        state of the editor session.

        Parameters
        ----------
        text : unicode
        func : Callable
        submenu : unicode | None

        """
        self.editorSession.menuPlugins.addPluginMenuItem(self.__class__, text, func, submenu)


class _CommandPlugins(QtCore.QObject):
    pluginRemoved = QtCore.Signal(object)
    pluginAdded = QtCore.Signal(object)

_CommandPlugins.instance = _CommandPlugins()

_registeredCommands = []


def registerPluginCommand(cls):
    if issubclass(cls, PluginCommand):
        _registeredCommands.append(cls)
    else:
        raise ValueError("Class %s must inherit from PluginCommand" % cls)
    return cls


class PluginsMenu(QtGui.QMenu):
    def __init__(self, editorSession):
        super(PluginsMenu, self).__init__()
        self.setTitle(self.tr("Plugins"))
        self.editorSession = editorSession
        self.submenus = {}
        _CommandPlugins.instance.pluginRemoved.connect(self.pluginRemoved)
        _CommandPlugins.instance.pluginAdded.connect(self.pluginAdded)
        self.plugins = []

        self.actionsByClass = defaultdict(list)

    def loadPlugins(self):
        for cls in _registeredCommands:
            instance = cls(self.editorSession)
            self.plugins.append(instance)

    def pluginAdded(self, cls):
        instance = cls(self.editorSession)
        self.plugins.append(instance)

    def pluginRemoved(self, cls):
        self.plugins = [p for p in self.plugins if not isinstance(p, cls)]

        for action in self.actionsByClass[cls]:
            self.removeAction(action)
            for menu in self.submenus.values():
                menu.removeAction(action)

    def addPluginMenuItem(self, cls, text, func, submenu=None):
        log.info("Adding menu item for cls %s text %s func %s", cls, text, func)
        if submenu is not None:
            if submenu not in self.submenus:
                menu = self.menuPlugins.addMenu(submenu)
                self.submenus[submenu] = menu
            else:
                menu = self.submenus[submenu]
        else:
            menu = self

        action = menu.addAction(text, func)

        self.actionsByClass[cls].append(action)
        log.info("Added action %s")
        return action
