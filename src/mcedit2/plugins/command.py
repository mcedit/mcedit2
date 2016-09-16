"""
    command
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from collections import defaultdict

from PySide import QtCore, QtGui

from mcedit2.command import SimpleRevisionCommand
from mcedit2.plugins.registry import PluginClassRegistry
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib.blocktypes import BlockType

log = logging.getLogger(__name__)


class CommandPlugin(QtCore.QObject):
    def __init__(self, editorSession):
        """
        A new CommandPlugin instance is created for each world opened in an editor
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
        super(CommandPlugin, self).__init__()
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


class SimpleCommandPlugin(CommandPlugin):
    """
    A simple type of command that covers a common use case: Display a dialog with a list
    of options and a pair of "Confirm" and "Cancel" buttons. When the "Confirm" button is
    pressed, `self.perform()` is called. The call to `perform` is automatically wrapped
    in a newly created undo entry.

    This function is passed an object containing the option values selected by the user.

    To define the list of options, set the `options` variable on the subclass of
    SimpleCommandPlugin. The options variable should be a list of dictionaries.
    """

    options = []
    displayName = NotImplemented
    submenuName = None

    def __init__(self, editorSession):
        super(SimpleCommandPlugin, self).__init__(editorSession)
        if self.displayName is NotImplemented:
            raise ValueError("self.displayName must be set.")

        self.addMenuItem(self.displayName, self.showDialog, self.submenuName)

    def showDialog(self):
        dialog = SimpleOptionsDialog(self.displayName, self.options, self.editorSession)
        result = dialog.exec_()
        if result == QtGui.QDialog.Accepted:
            command = SimpleRevisionCommand(self.editorSession, self.displayName)
            with self.editorSession.beginCommand(command):
                result = self.perform(self.editorSession.currentDimension,
                                      self.editorSession.currentSelection,
                                      dialog.getOptions())
            if result is not None:
                self.editorSession.placeSchematic(result, name=self.displayName)

    def perform(self, dimension, selection, options):
        """
        
        Parameters
        ----------
        dimension : mceditlib.worldeditor.WorldEditorDimension
        selection : mceditlib.selection.SelectionBox
        options : dict

        Returns
        -------
        progress: iterator or None
        """
        raise NotImplementedError


class SimpleOptionsDialog(QtGui.QDialog):
    def __init__(self, title, options, editorSession):
        super(SimpleOptionsDialog, self).__init__()
        self.setWindowTitle(title)

        self.editorSession = editorSession
        self.optIdx = 0

        self.optionsArea = QtGui.QScrollArea()
        self.optionsArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.optionsArea.setMinimumHeight(600)
        # self.optionsArea.setMinimumSize(500, 750)
        self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.setLayout(Column(self.optionsArea, self.buttonBox))
        self.containerWidget = QtGui.QWidget()
        self.containerWidget.setMinimumWidth(400)

        self.formLayout = QtGui.QFormLayout()
        self.valueGetters = {}
        self.widgets = []

        for opt in options:
            if isinstance(opt, tuple):
                optDict = dictFromFilterTuple(opt)
            elif isinstance(opt, dict):
                optDict = opt
            else:
                raise TypeError("SimpleOption must be tuple or dict")

            self.widgetFromOptDict(optDict)

        self.containerWidget.setLayout(self.formLayout)
        self.optionsArea.setWidget(self.containerWidget)


    def getOptions(self):
        values = {}
        for k, v in self.valueGetters.iteritems():
            values[k] = v()

        return values

    def widgetFromOptDict(self, optDict):
        self.optIdx += 1

        type = optDict.get('type')
        if type is None or not isinstance(type, basestring):
            raise ValueError("Option dict must have 'type' key")

        if type in ('int', 'float'):
            minimum = optDict.get('min', None)
            maximum = optDict.get('max', None)

            value = optDict.get('value', 0)
            increment = optDict.get('increment', None)
            
            name = optDict.get('name', None)
            if name is None:
                raise ValueError("Option dict must have 'name' key")

            text = optDict.get('text', "Option %d" % self.optIdx)
            if minimum is None or maximum is None:
                if type == 'float':
                    widget = QtGui.QDoubleSpinBox(value=value)
                else:
                    widget = QtGui.QSpinBox(value=value)
                if minimum is not None:
                    widget.setMinimum(minimum)
                else:
                    widget.setMinimum(-2000000000)
                if maximum is not None:
                    widget.setMaximum(maximum)
                else:
                    widget.setMaximum(2000000000)
                
                if increment is not None:
                    widget.setSingleStep(increment)
            else:
                widget = SpinSlider(double=(type == 'float'), minimum=minimum, maximum=maximum, value=value, increment=increment)

            self.widgets.append(widget)

            self.formLayout.addRow(text, widget)
            self.valueGetters[name] = widget.value

        elif type == 'bool':
            value = optDict.get('value', False)
            name = optDict.get('name', None)
            if name is None:
                raise ValueError("Option dict must have 'name' key")

            text = optDict.get('text', "Option %d" % self.optIdx)
            widget = QtGui.QCheckBox()
            widget.setChecked(value)
            self.widgets.append(widget)

            self.formLayout.addRow(text, widget)
            self.valueGetters[name] = widget.isChecked

        elif type == 'text':
            value = optDict.get('value', '')
            name = optDict.get('name', None)
            placeholder = optDict.get('placeholder', None)

            if name is None:
                raise ValueError("Option dict must have 'name' key")

            text = optDict.get('text', "Option %d" % self.optIdx)
            widget = QtGui.QLineEdit()
            self.widgets.append(widget)
            if placeholder:
                widget.setPlaceholderText(placeholder)
            if value:
                widget.setText(value)

            self.formLayout.addRow(text, widget)
            self.valueGetters[name] = widget.text

        elif type == 'choice':
            value = optDict.get('value', None)
            name = optDict.get('name', None)
            if name is None:
                raise ValueError("Option dict must have 'name' key")

            choices = optDict.get('choices', [])

            text = optDict.get('text', "Option %d" % self.optIdx)
            widget = QtGui.QComboBox()
            self.widgets.append(widget)

            for label, key in choices:
                widget.addItem(label, key)
                if key == value:
                    widget.setCurrentIndex(widget.count() - 1)

            def getChoiceKey():
                return widget.itemData(widget.currentIndex())

            self.formLayout.addRow(text, widget)
            self.valueGetters[name] = getChoiceKey

        elif type == 'blocktype':
            value = optDict.get('value', None)
            name = optDict.get('name', None)
            if name is None:
                raise ValueError("Option dict must have 'name' key")

            text = optDict.get('text', "Option %d" % self.optIdx)
            widget = BlockTypeButton()
            widget.editorSession = self.editorSession
            self.widgets.append(widget)

            if value is not None:
                if not isinstance(value, BlockType):
                    value = self.editorSession.worldEditor.blocktypes[value]
                widget.block = value

            self.formLayout.addRow(text, widget)
            self.valueGetters[name] = lambda: widget.block

        elif type == 'label':
            text = optDict.get('text', None)
            if not text:
                raise ValueError("Option dict for type 'label' must have 'text' key.")
            widget = QtGui.QLabel(text, wordWrap=True)
            self.widgets.append(widget)

            self.formLayout.addRow("", widget)

        elif type == 'nbt':
            widget = QtGui.QLabel("Not Implemented")
            self.widgets.append(widget)

            self.formLayout.addRow("NBT Option: ", widget)
        else:
            raise ValueError("Unknown type %s for option dict" % type)
        


def dictFromFilterTuple(opt):
    """
    Convert a filter-style option tuple to a new simple option dict.

    Parameters
    ----------
    opt : tuple

    Returns
    -------
    optDict : dict
    """



class _CommandPlugins(PluginClassRegistry):
    pluginClass = CommandPlugin

CommandPlugins = _CommandPlugins()


class PluginsMenu(QtGui.QMenu):
    def __init__(self, editorSession):
        super(PluginsMenu, self).__init__()
        self.setTitle(self.tr("Plugins"))
        self.editorSession = editorSession
        self.submenus = {}
        CommandPlugins.pluginRemoved.connect(self.pluginRemoved)
        CommandPlugins.pluginAdded.connect(self.pluginAdded)
        self.plugins = []

        self.actionsByClass = defaultdict(list)

    def loadPlugins(self):
        for cls in CommandPlugins.registeredPlugins:
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
        log.info("Added action %s", action)
        return action
