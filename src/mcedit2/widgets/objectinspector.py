"""
    objectinspector
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import weakref
import logging

from PySide import QtGui, QtCore

from mcedit2.util import settings
from mcedit2.widgets.layout import Row, Column


log = logging.getLogger(__name__)


class ObjectInspector(QtGui.QFrame):
    def __init__(self, *args, **kwargs):
        super(ObjectInspector, self).__init__(*args, **kwargs)
        self.treeWidget = QtGui.QTreeWidget()
        self.treeWidget.setHeaderLabels(["Attribute", "Type", "Value"])
        self.treeWidget.itemDoubleClicked.connect(self.itemDoubleClicked)
        self.treeWidget.restoreGeometry(settings.Settings().value("objectinspector/treewidget/geometry", ))

        self.inputBox = QtGui.QLineEdit(self.objectName)

        self.homeButton = QtGui.QPushButton("Home")
        self.homeButton.clicked.connect(self.goHome)

        self.editorButton = QtGui.QPushButton("Editor")
        self.editorButton.clicked.connect(self.goEditor)

        self.backButton = QtGui.QPushButton("Back")
        self.backButton.clicked.connect(self.goBack)

        self.reloadButton = QtGui.QPushButton("Reload")
        self.reloadButton.clicked.connect(self.updateTree)

        self.setLayout(Column((Row(self.homeButton,
                                   self.editorButton,
                                   self.backButton,
                                   self.reloadButton), 0),
                              (Row(QtGui.QLabel("Object: "),
                                   (self.inputBox, 1)), 0),
                              (self.treeWidget, 5)))

        self.inputBox.textChanged.connect(self.textDidChange)
        self.forwardHistory = []
        objectName = settings.Settings().value("objectinspector/objectname", self.objectName)
        self.history = settings.Settings().jsonValue("objectinspector/history", [objectName])
        self.historyLimit = 20

        self.goToObject(objectName)
    def close(self, *args, **kwargs):
        super(ObjectInspector, self).close(*args, **kwargs)
        settings.Settings().setValue("objectinspector/treewidget/geometry", self.treeWidget.saveGeometry())

    def goHome(self):
        self._goToObject(self.rootObjectName)

    def goEditor(self):
        from mcedit2 import editorapp
        self._goToObject(self.rootObjectName + ".sessions[%d]" % editorapp.MCEditApp.app.tabWidget.currentIndex())

    def goBack(self):
        if len(self.history) == 0:
            return
        self.forwardHistory.append(self.history.pop())
        back = self.history[-1]
        self.inputBox.setText(back)
        self._goToObject(back, history=False)
        log.info("Going back to %s", back)

    def textDidChange(self, text):
        if self.objectName != text:
            self._goToObject(text)
        else:
            self.updateTree()


    def goToObject(self, text):
        self.inputBox.setText(text)
        self._goToObject(text)

    def _goToObject(self, text, history=True):
        from mcedit2 import editorapp
        if editorapp.MCEditApp.app is None:
            log.info("editorApp is none, postponing...")
            QtCore.QTimer.singleShot(1000, lambda: (self._goToObject(text, history))) #try again later
            return

        self.objectName = text
        self.updateTree()
        if history:
            if self.history[-1] != self.objectName:
                log.info("Adding %s to history", self.objectName)
                self.history.append(self.objectName)
                self.history = self.history[:self.historyLimit]
                self.forwardHistory = []
                settings.Settings().setJsonValue("objectinspector/history", self.history)

        settings.Settings().setValue("objectinspector/objectname", text)

    def getObject(self):
        from mcedit2 import editorapp
        try:
            obj = eval(self.objectName, {'editorapp': editorapp}, {})
        except Exception as e:
            obj = e

        if obj is None:
            log.info("%s did not resolve to an object.", self.objectName)

        return obj

    def updateTree(self):
        def addObjectDict(obj, node, levels):
            for attr in sorted(obj.__dict__, key=str.lower):
                val = getattr(obj, attr)
                childNode = QtGui.QTreeWidgetItem([attr, type(val).__name__, repr(val)])
                childNode.objectName = node.objectName + "." + attr
                if isinstance(val, (list, tuple)):
                    for index, item in enumerate(val):
                        subchild = QtGui.QTreeWidgetItem([str(index), type(item).__name__, repr(item)])
                        childNode.addChild(subchild)
                        subchild.objectName = "%s[%d]" % (childNode.objectName, index)
                elif isinstance(val, dict):
                    for key, item in sorted(val.iteritems(), key=lambda x: x[0]):
                        subchild = QtGui.QTreeWidgetItem([repr(key), type(item).__name__, repr(item)])
                        childNode.addChild(subchild)
                        subchild.objectName = "%s[%r]" % (childNode.objectName, key)
                elif hasattr(val, "__dict__") and levels:
                    addObjectDict(val, childNode, levels-1)

                node.addChild(childNode)
                if hasattr(val, "__len__") and len(val) < collectionLimit:
                    childNode.setExpanded(False)

        collectionLimit = 20
        tw = self.treeWidget
        tw.clear()
        obj = self.getObject()
        if obj is None:
            rootNode = QtGui.QTreeWidgetItem([self.objectName, "[dead]", "Dead object"])
            tw.addTopLevelItem(rootNode)
            return
        else:
            rootNode = QtGui.QTreeWidgetItem([self.objectName, obj.__class__.__name__, repr(obj)])

        tw.addTopLevelItem(rootNode)
        rootNode.objectName = self.objectName
        if hasattr(obj, "__dict__"):
            addObjectDict(obj, rootNode, 0)

        rootNode.setExpanded(True)
        tw.resizeColumnToContents(0)
        tw.resizeColumnToContents(1)


    rootObjectName = "editorapp.MCEditApp.app"
    objectName = rootObjectName

    def itemDoubleClicked(self, item):
        self.goToObject(item.objectName)

