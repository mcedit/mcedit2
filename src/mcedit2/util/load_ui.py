"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtUiTools, QtCore, QtGui

from mcedit2.util.resources import resourcePath


log = logging.getLogger(__name__)

_customWidgetClasses = {}


class MCEUILoader(QtUiTools.QUiLoader):
    def __init__(self, baseinstance=None, *a, **kw):
        super(MCEUILoader, self).__init__(*a, **kw)
        self.baseinstance = baseinstance

    def createWidget(self, className, parent=None, name=""):
        """
        QWidget * QUiLoader::createWidget ( const QString & className, QWidget * parent = 0, const QString & name = QString() ) [virtual]

        :param className: str
        :param parent: QWidget
        :param name: str

        :return:
        :rtype:
        """
        if parent is None and self.baseinstance:
            return self.baseinstance

        customClass = _customWidgetClasses.get(className)
        if customClass is not None:
            obj = customClass(parent)
            if name and parent is not None:
                setattr(parent, name, obj)
            return obj
        else:
            return super(MCEUILoader, self).createWidget(className, parent, name)


def registerCustomWidget(cls):
    name = cls.__name__
    _customWidgetClasses[name] = cls
    return cls


def unregisterCustomWidget(cls):
    _customWidgetClasses.pop(cls.__name__, None)


def load_ui(name, parent=None, baseinstance=None):
    loader = MCEUILoader(baseinstance=baseinstance)
    loader.setWorkingDirectory(resourcePath(os.path.join("mcedit2", "ui")))
    path = resourcePath("mcedit2/ui/" + name)
    uifile = QtCore.QFile(path)
    uifile.open(QtCore.QFile.ReadOnly)
    widget = loader.load(uifile, parent)
    uifile.close()
    assert isinstance(widget, QtGui.QWidget)
    # if not hasattr(sys, 'frozen'):
    #     log.info("Adding debug context menu: %s", name)
    #
    #     def showUISource():
    #         url = QtCore.QUrl.fromLocalFile(os.path.dirname(path))
    #         QtGui.QDesktopServices.openUrl(url)
    #
    #     def showCallerSource():
    #         cmd = r'C:\Program Files (x86)\JetBrains\PyCharm Community Edition 3.1\bin\pycharm.exe'
    #         args = [cmd, callerFile, b'--line', b"%s" % callerLine]
    #         subprocess.Popen(args,
    #                          stdin = None,
    #                          stdout = None,
    #                          stderr = None,
    #                          #shell=platform.system() == 'Windows'
    #                          )
            #os.system(" ".join([cmd, callerFile, '/l', "%s" % callerLine]))
            #log.warn("ARGS: %s", args)

        # if widget.contextMenuPolicy() == Qt.DefaultContextMenu:
        #     widget.setContextMenuPolicy(Qt.ActionsContextMenu)
        #     showUISourceAction = QtGui.QAction("Reveal .ui file", widget, triggered=showUISource)
        #     widget.addAction(showUISourceAction)
        #     frame = inspect.currentframe()
        #     frame = frame.f_back
        #     callerFile = frame.f_code.co_filename
        #     callerLine = frame.f_lineno


        # showCallerSourceAction = QtGui.QAction("Open source code", widget, triggered=showCallerSource)
        # widget.addAction(showCallerSourceAction)

    return widget
