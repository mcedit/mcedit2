"""
    chest
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui
from mcedit2.widgets.inventory import InventoryEditor
from mcedit2.widgets.layout import Column

log = logging.getLogger(__name__)

class GenericContainerEditorWidget(QtGui.QWidget):
    def __init__(self, slotLayout, editorSession, tileEntityRef):
        super(GenericContainerEditorWidget, self).__init__()
        assert tileEntityRef.id == self.tileEntityID

        self.inventoryEditor = InventoryEditor(slotLayout)
        self.inventoryEditor.editorSession = editorSession

        self.setLayout(Column(self.inventoryEditor))

        self.tileEntityRef = tileEntityRef

        self.inventoryEditor.inventoryRef = self.getItemsRef()

    def getItemsRef(self):
        return self.tileEntityRef.Items

CHEST_SLOT_LAYOUT = [(s % 9, s // 9, s) for s in range(27)]

class ChestEditorWidget(GenericContainerEditorWidget):
    tileEntityID = "Chest"
    def __init__(self, editorSession, tileEntityRef):
        super(ChestEditorWidget, self).__init__(CHEST_SLOT_LAYOUT, editorSession, tileEntityRef)
        self.displayName = self.tr("Chest")


DISPENSER_SLOT_LAYOUT = [(s % 3, s // 3, s) for s in range(9)]

class DispenserEditorWidget(GenericContainerEditorWidget):
    tileEntityID = "Trap"
    def __init__(self, editorSession, tileEntityRef):
        super(DispenserEditorWidget, self).__init__(DISPENSER_SLOT_LAYOUT, editorSession, tileEntityRef)
        self.displayName = self.tr("Dispenser")


HOPPER_SLOT_LAYOUT = [(s, 0, s) for s in range(5)]

class HopperEditorWidget(GenericContainerEditorWidget):
    tileEntityID = "Hopper"
    def __init__(self, editorSession, tileEntityRef):
        super(HopperEditorWidget, self).__init__(HOPPER_SLOT_LAYOUT, editorSession, tileEntityRef)
        self.displayName = self.tr("Hopper")
