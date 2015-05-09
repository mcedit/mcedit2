from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui
from PySide.QtCore import Qt


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
        if isinstance(item, (int, float)):
            box.addSpacing(item)
        if item is None:
            box.addStretch()

    return box

def Row(*a, **kw):
    """
    :rtype: QtGui.QHBoxLayout
    """
    margin = kw.pop('margin', None)
    box = QtGui.QHBoxLayout(**kw)
    _Box(box, *a)
    if margin is not None:
        box.setContentsMargins(margin, margin, margin, margin)
    return box


def Column(*a, **kw):
    """
    :rtype: QtGui.QVBoxLayout
    """
    margin = kw.pop('margin', None)
    box = QtGui.QVBoxLayout(**kw)
    _Box(box, *a)
    if margin is not None:
        box.setContentsMargins(margin, margin, margin, margin)
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
