"""
    objgraphwidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import contextlib
import inspect
import os
import tempfile
import logging
import gc

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.rendering.scenegraph import rendernode
from mcedit2.util import settings
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)

try:
    import objgraph
except ImportError:
    objgraph = None

inputSetting = settings.Settings().getOption("objgraph/input", unicode)

class ObjGraphWidget(QtGui.QWidget):
    def __init__(self, *a, **kw):
        super(ObjGraphWidget, self).__init__(*a, **kw)

        if objgraph is None:
            self.setLayout(Row(QtGui.QLabel("objgraph is not installed (and you probably don't have GraphViz "
                                            "either...) "), None))
            return

        self.inputWidget = QtGui.QLineEdit()
        self.inputWidget.setText(inputSetting.value(""))
        self.inputWidget.textChanged.connect(inputSetting.setValue)
        self.listWidget = QtGui.QListWidget()
        self.scrollArea = QtGui.QScrollArea()
        self.imageView = QtGui.QLabel()
        #self.scrollArea.setMinimumSize(300, 300)
        self.scrollArea.setWidget(self.imageView)

        for name, count in objgraph.most_common_types(100):
            item = QtGui.QListWidgetItem()
            item.setText("%s (%d)" % (name, count))
            item.setData(Qt.UserRole, name)
            self.listWidget.addItem(item)

        self.listWidget.itemSelectionChanged.connect(self.itemChanged)
        refsButton = QtGui.QPushButton("Refs", clicked=self.showRefs)
        backrefsButton = QtGui.QPushButton("Backrefs", clicked=self.showBackrefs)
        graphButton = QtGui.QPushButton("Graph", clicked=self.showGraph)
        garbageButton = QtGui.QPushButton("Garbage", clicked=self.showGarbage)

        inputRow = Row(self.inputWidget, refsButton, backrefsButton, garbageButton, graphButton)
        self.widthLimitBox = QtGui.QSpinBox(value=14)
        self.depthLimitBox = QtGui.QSpinBox(value=7)
        limitRow = Row(QtGui.QLabel("Graph Width"), self.widthLimitBox, QtGui.QLabel("Graph Depth"), self.depthLimitBox)
        self.setLayout(Column(inputRow, limitRow, self.listWidget, (self.scrollArea, 1)))
        self.setMinimumSize(800, 600)

    def itemChanged(self):
        items = self.listWidget.selectedItems()
        if len(items) == 0:
            return

        objType = items[0].data(Qt.UserRole)
        self.inputWidget.setText(objType)
        self.showBackrefs()

    @contextlib.contextmanager
    def showTempImage(self):
        fn = tempfile.mktemp('chain.png')
        #fn = "graph.png"
        yield fn
        if os.path.exists(fn):
            image = QtGui.QImage(fn)
            self.imageView.setPixmap(QtGui.QPixmap(image))
            self.imageView.setFixedSize(image.size())
            os.unlink(fn)
        else:
            icon = QtGui.QIcon.fromTheme("dialog-error")
            self.imageView.setPixmap(icon.pixmap(64, 64))

    def filterPrimitives(self, obj):
        return not isinstance(obj, (str, unicode, int, float, QtCore.Signal)) and obj is not None

    def showGarbage(self):
        with self.showTempImage() as fn:
            objgraph.show_refs(gc.garbage,
                               filter=self.filterPrimitives,
                               max_depth=self.depthLimitBox.value(),
                               too_many=self.widthLimitBox.value(), filename=fn)

    def showRefs(self):
        objType = str(self.inputWidget.text())
        with self.showTempImage() as fn:
            objgraph.show_refs(objgraph.by_type(objType),
                               filter=self.filterPrimitives,
                               max_depth=self.depthLimitBox.value(),
                               too_many=self.widthLimitBox.value(), filename=fn)

    def showBackrefs(self):
        objType = str(self.inputWidget.text())
        with self.showTempImage() as fn:
            objects = objgraph.by_type(objType)
            if len(objects) == 0:
                return
            objgraph.show_backrefs(objects[0],
                                   max_depth=self.depthLimitBox.value(),
                                   extra_ignore=(id(gc.garbage),id(objects)),
                                   too_many=self.widthLimitBox.value(), filename=fn)

    def showGraph(self):
        from mcedit2 import editorapp
        editorApp = editorapp.MCEditApp.app
        objName = str(self.inputWidget.text()) or "editorApp"
        try:
            obj = eval(objName)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return

        if isinstance(obj, rendernode.RenderNode):
            def edge_func(x):
                return x.children
        else:
            def edge_func(x):
                return gc.get_referents(x)

        with self.showTempImage() as fn:
            objgraph.show_graph(obj, edge_func=edge_func, swap_source_target=True,
                                extra_ignore=(str, int),
                max_depth=self.depthLimitBox.value(),
                too_many=self.widthLimitBox.value(), filename=fn, filter=lambda x: not inspect.isclass(x))
        "editorApp.sessions[0].editorTab.views[5].worldView.renderGraph"
