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
    def __init__(self, settings, key, valueType=None, default=None, *args, **kwargs):
        super(MCESettingsOption, self).__init__(*args, **kwargs)
        self.settings = settings
        self.key = key
        self.valueType = valueType
        self.default = default

    def value(self, default=None):
        if default is None:
            default = self.default

        if self.valueType == "json":
            value = self.settings.jsonValue(self.key, default)
        else:
            value = self.settings.value(self.key, default)
            if self.valueType is bool:
                if isinstance(value, basestring):
                    value = value.lower() == "true"
            elif self.valueType:
                value = self.valueType(value)
        return value

    def setValue(self, value):
        if self.valueType == "json":
            return self.settings.setJsonValue(self.key, value)
        else:
            return self.settings.setValue(self.key, value)

    valueChanged = QtCore.Signal(object)

    def jsonValue(self, default=None):
        return self.settings.jsonValue(self.key, default)

    def setJsonValue(self, value):
        return self.settings.setJsonValue(self.key, value)

    def connectAndCall(self, callback):
        """
        Connect `callback` to this option's `valueChanged` signal, then call it with the value of this option.

        :param callback:
        :type callback:
        :return:
        :rtype:
        """
        self.valueChanged.connect(callback)
        callback(self.value())

class MCESettingsNamespace(object):
    def __init__(self, rootSettings, prefix):
        self.rootSettings = rootSettings
        if not prefix.endswith("/"):
            prefix = prefix + "/"

        self.prefix = prefix

    def getOption(self, key, type=None, default=None):
        """
        Parameters
        ----------
        key: str
        type: bool | int | float | str
        default: Any

        Returns
        -------

        option: MCESettingsOption
        """
        return self.rootSettings.getOption(self.prefix + key, type, default)


class MCESettings(QtCore.QSettings):

    def __init__(self, *args, **kwargs):
        """
        Subclass of QSettings. Adds a `getOption` method which returns an individual option as its own object. Adds
        one signal for each setting, emitted when its value is changed. Also provides json encoded methods to work
        around a bug in PySide.

        QSettings, under PySide, does not reliably infer that a settings value should be read as a QStringList.
        jsonValue and setJsonValue methods are provided that will automatically encode/decode the given value to or from json

        :rtype: MCESettings
        """
        dataDir = directories.getUserFilesDirectory()
        iniPath = os.path.join(dataDir, "mcedit2.ini")
        log.info("Loading app settings from %s", iniPath)
        super(MCESettings, self).__init__(iniPath, QtCore.QSettings.IniFormat, *args,
                                           **kwargs)
        self.options = {}
        #= defaultdict(lambda: QtCore.Signal(object))

    def getNamespace(self, prefix):
        """
        Return an MCESettingsNamespace object which can be used to access settings whose keys are all prefixed by
        the given prefix

        :param prefix:
        :type prefix:
        :return:
        :rtype:
        """
        return MCESettingsNamespace(self, prefix)

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
        old = self.value(key)
        if old != val:
            log.info("Setting %r changed to (%.40r)(...) (was (%.40r)(...))", key, val, old)
            super(MCESettings, self).setValue(key, val)
            self.emitSignal(key, val)

    def jsonValue(self, key, default=None):
        value = self.value(key, None)
        if value is not None:
            try:
                return json.loads(value)
            except ValueError as e:  # No JSON object could be decoded
                log.error("Failed to decode setting %s: %s", key, e)
                return default
        else:
            return default

    def setJsonValue(self, key, value):
        self.setValue(key, json.dumps(value))

    def getOption(self, key, type=None, default=None):
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

        option = MCESettingsOption(self, key, type, default)
        self.options[key] = option
        return option


