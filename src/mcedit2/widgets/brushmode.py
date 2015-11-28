"""
    brushmode
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools.tool_settings import BrushModeSetting

log = logging.getLogger(__name__)


class BrushModeWidget(QtGui.QComboBox):
    def __init__(self, *args, **kwargs):
        super(BrushModeWidget, self).__init__(*args, **kwargs)
        self.currentIndexChanged.connect(self.indexDidChange)
        self.adding = False

    def setModes(self, modes):
        self.adding = True
        try:
            for mode in modes:
                self.addItem(mode.displayName, mode.name)

            currentID = BrushModeSetting.value()
            currentIndex = self.findData(currentID)
            if currentIndex == -1:
                log.info("Search failed!")
                currentIndex = 0
            log.info("Loading BrushModeWidget setting: found %s at %s", currentID, currentIndex)
            self.setCurrentIndex(currentIndex)
        finally:
            self.adding = False

    def indexDidChange(self):
        if self.adding:
            return
        BrushModeSetting.setValue(self.itemData(self.currentIndex()))