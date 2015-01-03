"""
    objgraphwidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import contextlib
import inspect
import os
import tempfile
from PySide import QtGui
import logging
from PySide.QtCore import Qt
import gc
from mcedit2.rendering import rendergraph
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)

try:
    import objgraph
except ImportError:
    objgraph = None

class ObjGraphWidget(QtGui.QWidget):
    def __init__(self, *a, **kw):
        super(ObjGraphWidget, self).__init__(*a, **kw)

        if objgraph is None:
            self.setLayout(Row(QtGui.QLabel("objgraph is not installed (andyou probably don't have GraphViz "
                                            "either...) "), None))
            return

        self.inputWidget = QtGui.QLineEdit()

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
        image = QtGui.QImage(fn)
        self.imageView.setPixmap(QtGui.QPixmap(image))
        self.imageView.setFixedSize(image.size())
        os.unlink(fn)

    def showGarbage(self):
        with self.showTempImage() as fn:
            objgraph.show_refs(gc.garbage, filename=fn)

    def showRefs(self):
        objType = str(self.inputWidget.text())
        with self.showTempImage() as fn:
            objgraph.show_refs(objgraph.by_type(objType), filename=fn)

    def showBackrefs(self):
        objType = str(self.inputWidget.text())
        with self.showTempImage() as fn:
            objgraph.show_chain(objgraph.find_backref_chain(objgraph.by_type(objType)[0],
                                                            objgraph.is_proper_module),
                                filename=fn)

    def showGraph(self):
        from mcedit2 import editorapp
        editorApp = editorapp.MCEditApp.app
        objName = str(self.inputWidget.text()) or "editorApp"
        obj = eval(objName)
        if isinstance(obj, rendergraph.RenderNode):
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
