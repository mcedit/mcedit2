"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import time
import weakref

from PySide import QtGui

from mcedit2.widgets.layout import Column


log = logging.getLogger(__name__)

class InfoPanel(QtGui.QWidget):
    def __init__(self, attrs, signals, **kwargs):
        """
        Create a widget that displays a list of an object's selected attributes, named in `attrs`.
        The widget updates itself whenever one of the object's signals named in `signals` is emitted.

        If an attribute named in `attrs` is not found on `object`, the InfoPanel instance is checked for
        an attribute of the same name and it is used instead if found.

        :type attrs: list of attribute names to display
        :type signals: list of signals to monitor
        :param kwargs: args for QWidget
        :type kwargs:
        """
        QtGui.QWidget.__init__(self, **kwargs)
        self.attrs = attrs
        self.signals = signals
        self.lastUpdate = time.time()
        self.labels = [QtGui.QLabel() for _ in attrs]

        self.setLayout(Column(*self.labels))

    def updateLabels(self):
        now = time.time()
        if now < self.lastUpdate + 0.25:
            return
        self.lastUpdate = now
        if self.object:
            for attr, label in zip(self.attrs, self.labels):
                try:
                    value = getattr(self.object, attr)
                except AttributeError:  # catches unrelated AttributeErrors in property getters...
                    try:
                        value = getattr(self, attr)
                    except AttributeError:
                        log.exception("Error updating info panel.")
                        value = getattr(self, attr, "Attribute not found")
                label.setText("%s: %s" % (attr, value))

    _object = None
    @property
    def object(self):
        return self._object()

    @object.setter
    def object(self, value):
        self._object = weakref.ref(value)
        self.updateLabels()

        for signal in self.signals:
            signal = getattr(self.object, signal, None)
            if signal:
                signal.connect(self.updateLabels)

    setObject = object.setter
