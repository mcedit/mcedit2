"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from mcedit2.util.settings import Settings

log = logging.getLogger(__name__)


_binding_names = {}


def ChangeBinding(shortcutName, shortcutString):
    settings = Settings()
    settings.setValue("keybinding/" + shortcutName, shortcutString)


class MCEAction(QtGui.QAction):
    def __init__(self, name, parent, shortcutName=None, *args, **kwargs):
        super(MCEAction, self).__init__(name, parent, *args, **kwargs)
        self.shortcutName = shortcutName
        if shortcutName:
            settings = Settings()
            settingsKey = "keybinding/" + shortcutName
            option = settings.getOption(settingsKey)

            _binding_names[shortcutName] = name

            shortcutString = option.value()
            if shortcutString is not None:
                self.setShortcut(QtGui.QKeySequence(shortcutString))

            option.valueChanged.connect(self.shortcutChanged)

    def shortcutChanged(self, shortcutString):
        self.setShortcut(QtGui.QKeySequence(shortcutString))
