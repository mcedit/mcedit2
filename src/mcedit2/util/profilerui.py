"""
    profilerui
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore

from mcedit2.util import profiler
from mcedit2.widgets.layout import Column


log = logging.getLogger(__name__)

class ProfilerWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(ProfilerWidget, self).__init__(*args, **kwargs)

        self.treeWidget = treeWidget = QtGui.QTreeWidget()
        self.treeWidget.setAlternatingRowColors(True)
        columns = ("name", "time", "%", "%%", "#", "/")
        #table.setColumnCount(len(columns))
        treeWidget.setHeaderLabels(columns)

        #row = Row()
        #row.addSpacing()
            #row.addWidget(refreshButton)

        self.setLayout(Column(self.treeWidget))
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.updateTable)
        self.updateTimer.setInterval(1000)
        self.updateTimer.start()
        self.updateTable()

    @profiler.function("updateProfilerView")
    def updateTable(self):
        if not self.treeWidget.isVisible():
            return

        treeWidget = self.treeWidget
        treeWidget.clear()
        analysis = profiler.getProfiler().analyze()

        tree = analysis["root"]

        root = QtGui.QTreeWidgetItem(["root", "%.2f" % tree.totalTime])

        def processNode(node, item):
            nodeTime = node.totalTime
            items = node.items()

            accountedTime = sum(leaf.totalTime for leaf in node.itervalues())
            if accountedTime < nodeTime and len(items):
                otherNode = profiler.AnalysisNode()
                otherNode.samples.append(nodeTime - accountedTime)
                items.append(("(other)", otherNode))

            sortedItems = sorted(items, key=lambda (name, leaf): leaf.totalTime, reverse=True)
            for name, leaf in sortedItems:
                if nodeTime:
                    percentOfParent = leaf.totalTime / nodeTime * 100
                else:
                    percentOfParent = 0

                if tree.totalTime:
                    percentOfTotal = leaf.totalTime / tree.totalTime * 100
                else:
                    percentOfTotal = 0

                leafItem = QtGui.QTreeWidgetItem([name,
                                                  "%.2f" % leaf.totalTime,
                                                  "%.1f%%" % percentOfParent,
                                                  "%.1f%%" % percentOfTotal,
                                                  "%d" % leaf.ncalls,
                                                  "%f" % (leaf.ncalls / tree.totalTime)])
                item.addChild(leafItem)
                processNode(leaf, leafItem)

        processNode(tree, root)
        treeWidget.addTopLevelItem(root)
        treeWidget.expandAll()
        for i in range(treeWidget.columnCount()):
            treeWidget.resizeColumnToContents(i)

