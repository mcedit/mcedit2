from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import time

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.ui.log_view import Ui_logView
from mcedit2.util.settings import Settings


log = logging.getLogger(__name__)
rootlog = logging.getLogger()

class LogHandler(logging.Handler):
    def __init__(self, model):
        super(LogHandler, self).__init__(level=logging.INFO)
        self.model = model

    #@profiler.decorate("logRecorder")
    def emit(self, logrecord):
        self.model.add_logrecord(logrecord)

def logError(func):
    def _func(*a, **kw):
        try:
            func(*a, **kw)
        except Exception as e:
            log.exception("%s\n", e)

    return _func


class LogModel(QtCore.QAbstractTableModel):
    def __init__(self, *args, **kwargs):
        QtCore.QAbstractTableModel.__init__(self, *args, **kwargs)

        self.logLimit = 1000
        rootlog.addHandler(LogHandler(self))

        self.last_record = None
        self.records = []

    log_colors = {
        #logging.DEBUG: (QtGui.QColor("white").darker(), QtGui.QColor("white")),
        logging.INFO: (QtGui.QColor("black"), QtGui.QColor("white")),
        logging.WARN: (QtGui.QColor("black"), QtGui.QColor("yellow").lighter()),
        logging.ERROR: (QtGui.QColor("red"), QtGui.QColor("white")),
        logging.CRITICAL: (QtGui.QColor("red"), QtGui.QColor("white")),
        }

    def add_logrecord(self, record):
        """
        :type record: logging.LogRecord
        """
        def clean_msg(msg):
            return msg.replace("\n", "")

        count = len(self.records)
        record.repeat_count = 1

        if self.last_record:
            if record.getMessage() == self.last_record.getMessage():
                item = self.records[-1]
                self.last_record.repeat_count += 1
                item.setText("%s (repeated %s times)" % (clean_msg(self.last_record.getMessage()),
                                                         self.last_record.repeat_count))
                return

        if record.levelno == logging.DEBUG:
            return

        fg, bg = self.log_colors[record.levelno]

        item = QtGui.QStandardItem(clean_msg(record.getMessage()))

        try:
            item.setForeground(QtGui.QBrush(fg))
            item.setBackground(QtGui.QBrush(bg))
            item.record_levelno = record.levelno
            item.record_name = record.name
        except AttributeError as e:
            # WTF: AttributeError: 'PySide.QtOpenGL.QGLContext' object has no attribute 'setData'
            import pdb; pdb.set_trace()

        self.beginInsertRows(QtCore.QModelIndex(), len(self.records), len(self.records))
        self.records.append(item)
        self.endInsertRows()

        if count > self.logLimit:
            self.beginRemoveRows(QtCore.QModelIndex(), 0, 0)
            self.records.pop(0)
            self.endRemoveRows()

        self.last_record = record
        self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex())

    def rowCount(self, parent, index = QtCore.QModelIndex()):
        """

        :type index: QtCore.QModelIndex
        """
        return len(self.records)

    def columnCount(self, parent, index = QtCore.QModelIndex()):
        """

        :type index: QtCore.QModelIndex
        """
        return 1

    def data(self, index, role=Qt.DisplayRole):
        item = self.records[index.row()]
        return item.data(role)


class LogViewProxyModel(QtGui.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(LogViewProxyModel, self).__init__(*args, **kwargs)

        self.blockedLevels = set()
        self.blockedNames = set()

    def filterAcceptsRow(self, row, parent):
        item = self.sourceModel().records[row]
        return not (item.record_levelno in self.blockedLevels or item.record_name in self.blockedNames)


def LogViewFrame(parent):
    class _LogViewFrame(QtGui.QWidget, Ui_logView):
        pass

    logWidget = _LogViewFrame()
    logWidget.setupUi(logWidget)

    moduleNames = set()

    logListModel = LogModel()
    logListView = logWidget.logListView
    logListView.autoScrollLog = True

    assert isinstance(logListView, QtGui.QListView)

    proxy = LogViewProxyModel()
    proxy.setSourceModel(logListModel)
    logListView.setModel(proxy)

#    obj = logListView.__class__
#    for name2 in dir(obj):
#        obj2 = getattr(obj, name2)
#        if isinstance(obj2, QtCore.Signal):
#            print ("SIGNAL", name2)

    def sliderMoved(value):
        #log.debug("sliderMoved %s %s", value, logListView.verticalScrollBar().maximum())
        logListView.autoScrollLog = (logListView.verticalScrollBar().maximum() - value < 4.0)

    logListView.verticalScrollBar().valueChanged.connect(sliderMoved)

    logListView.lastScrollTime = time.time()

    def updateLog():
        if logListView.autoScrollLog:
            # QListView.scrollToBottom is expensive! Only call it once per second.
            t = time.time()
            if logListView.lastScrollTime + 1 < t:
                logListView.lastScrollTime = t
                logListView.scrollToBottom()

        #for item in logListModel.records:
        #    name = item.record.name
        #    if name not in moduleNames:
        #        moduleNames.add(name)
        #        logWidget.moduleNamesBox.addItem(name)

    logWidget.updateLog = updateLog
    logListModel.dataChanged.connect(updateLog)


    def toggleLevel(level):
        def _toggle(checked):
            if checked:
                proxy.blockedLevels.discard(level)
            else:
                proxy.blockedLevels.add(level)

            proxy.invalidateFilter()
            updateLog()
            setValue(level, checked)
        return _toggle

    settings = Settings()

    def getValue(level, default):
        return int(settings.value("log/showlevel/%s" % logging.getLevelName(level), default))

    def setValue(level, value):
        settings.setValue("log/showlevel/%s" % logging.getLevelName(level), int(value))

    def setup(button, level):
        button.toggled.connect(toggleLevel(level))
        button.setChecked(bool(getValue(level, 1)))

    setup(logWidget.debugsButton, logging.DEBUG)
    setup(logWidget.infosButton, logging.INFO)
    setup(logWidget.warningsButton, logging.WARN)
    setup(logWidget.errorsButton, logging.ERROR)
    setup(logWidget.errorsButton, logging.CRITICAL)

    return logWidget
