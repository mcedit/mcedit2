from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui


def _Box(box, *a):
    for arg in a:
        if isinstance(arg, tuple):
            item = arg[0]
        else:
            item = arg
            arg = (item,)

        if isinstance(item, QtGui.QLayout):
            box.addLayout(*arg)
        if isinstance(item, QtGui.QWidget):
            box.addWidget(*arg)
        if item is None:
            box.addStretch()

    return box

def Row(*a, **kw):
    """
    :rtype: QHBoxLayout
    """
    margin = kw.pop('margin', None)
    box = QtGui.QHBoxLayout(**kw)
    if margin:
        box.setContentsMargins((margin,) * 4)
    _Box(box, *a)
    return box


def Column(*a, **kw):
    """
    :rtype: QtGui.QVBoxLayout
    """
    margin = kw.pop('margin', None)
    box = QtGui.QVBoxLayout(**kw)
    if margin:
        box.setContentsMargins((margin,) * 4)
    _Box(box, *a)
    return box

def setWidgetError(widget, exc):
    """
    Add a subwidget to `widget` that displays the error message for the exception `exc`
    :param widget:
    :param exc:
    :return:
    """
    layout = QtGui.QVBoxLayout()
    layout.addWidget(QtGui.QLabel(exc.message))
    layout.addStretch()
    widget.setLayout(layout)
