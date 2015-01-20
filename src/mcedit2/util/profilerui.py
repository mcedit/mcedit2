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
        columns = ("name", "time", "self", "%", "#", "per call")
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

        accountedTime = sum(subleaf.totalTime for subleaf in tree.itervalues())
        if accountedTime < tree.totalTime and len(tree.items()):
            selfTime = tree.totalTime - accountedTime
        else:
            selfTime = 0
        if tree.totalTime:
            selfPercent = selfTime / tree.totalTime * 100
        else:
            selfPercent = 0

        root = QtGui.QTreeWidgetItem(["root",
                                      "%.2f" % tree.totalTime,
                                      "%.1f%%" % selfPercent,
                                      "100%",
                                      "1",
                                      "%0.3f ms" % (1000 * tree.totalTime)
                                      ])

        def processNode(node, item):
            items = node.items()

            sortedItems = sorted(items, key=lambda (name, leaf): leaf.totalTime, reverse=True)
            for name, leaf in sortedItems:
                if tree.totalTime:
                    percentOfTotal = leaf.totalTime / tree.totalTime * 100
                else:
                    percentOfTotal = 0

                accountedTime = sum(subleaf.totalTime for subleaf in leaf.itervalues())
                if accountedTime < leaf.totalTime and len(items):
                    selfTime = leaf.totalTime - accountedTime
                else:
                    selfTime = 0
                selfPercent = 100 if tree.totalTime == 0 else (selfTime / tree.totalTime * 100)

                leafItem = QtGui.QTreeWidgetItem([name,
                                                  "%.2f" % leaf.totalTime,
                                                  "%.1f%%" % selfPercent,
                                                  "%.1f%%" % percentOfTotal,
                                                  "%d" % leaf.ncalls,
                                                  "%0.3f ms" % (0 if leaf.ncalls == 0 else (1000 * leaf.totalTime / leaf.ncalls))])
                item.addChild(leafItem)
                processNode(leaf, leafItem)

        processNode(tree, root)
        treeWidget.addTopLevelItem(root)
        treeWidget.expandAll()
        for i in range(treeWidget.columnCount()):
            treeWidget.resizeColumnToContents(i)

