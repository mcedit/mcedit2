"""
    settings
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import json
import os
from PySide import QtCore
import logging
from mcedit2.util import directories

log = logging.getLogger(__name__)

_settings = None


def Settings():
    global _settings
    if _settings is None:
        _settings = MCESettings()

    return _settings


class MCESettingsOption(QtCore.QObject):
    def __init__(self, settings, key, type, *args, **kwargs):
        super(MCESettingsOption, self).__init__(*args, **kwargs)
        self.settings = settings
        self.key = key
        self.type = type

    def value(self, default=None):
        value = self.settings.value(self.key, default)
        if self.type:
            value = self.type(value)
        return value

    def setValue(self, value):
        return self.settings.setValue(self.key, value)

    valueChanged = QtCore.Signal(object)

    def jsonValue(self, default=None):
        return self.settings.jsonValue(self.key, default)

    def setJsonValue(self, value):
        return self.settings.setJsonValue(self.key, value)



class MCESettings(QtCore.QSettings):
    """
    Subclass of QSettings. Adds a `getOption` method which returns an individual option as its own object. Adds
    one signal for each setting, emitted when its value is changed. Also provides json encoded methods to work
    around a bug in PySide.

    QSettings, under PySide, does not reliably infer that a settings value should be read as a QStringList.
    jsonValue and setJsonValue methods are provided that will automatically encode/decode the given value to or from json

    """
    def __init__(self, *args, **kwargs):
        dataDir = directories.getUserFilesDirectory()
        super(MCESettings, self).__init__(os.path.join(dataDir, "mcedit2.ini"), QtCore.QSettings.IniFormat, *args,
                                           **kwargs)
        self.options = {}
        #= defaultdict(lambda: QtCore.Signal(object))

    def getSignal(self, key):
        """
        Returns a signal to be triggered when the setting `key` is changed.
        The signal handler receives one argument: the setting's new value.

        :param key: Settings key
        :type key: str
        :rtype: None
        """
        return self.getOption(key).valueChanged

    def emitSignal(self, key, val):
        option = self.options.get(key)
        if option:
            option.valueChanged.emit(val)

    def setValue(self, key, val):
        old = self.value(key, val)
        super(MCESettings, self).setValue(key, val)
        if old != val:
            self.emitSignal(key, val)

    def jsonValue(self, key, default=None):
        value = self.value(key, None)
        if value is not None:
            try:
                return json.loads(value)
            except ValueError:  # No JSON object could be decoded
                return default
        else:
            return default

    def setJsonValue(self, key, value):
        self.setValue(key, json.dumps(value))

    def getOption(self, key, type=None):
        """
        Return an object that represents the setting at 'key'. The object may be used to get and set the value and
        get the value's valueChanged signal. Among other uses, the object's setValue attribute may be connected to the
        valueChanged signal of an input field.

        :param key:
        :type key:
        :return:
        :rtype:
        """
        option = self.options.get(key)
        if option:
            return option

        option = MCESettingsOption(self, key, type)
        self.options[key] = option
        return option


