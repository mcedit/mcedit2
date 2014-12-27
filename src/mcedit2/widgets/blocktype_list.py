"""
    blocktype_list
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui, QtCore
import logging
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

class BlockListWidget(QtGui.QWidget):
    def __init__(self, blocktypes, textureAtlas, blocksToShow=None):
        """

        :param blocktypes:
        :type blocktypes: mceditlib.blocktypes.BlockTypeSet
        :param textureAtlas:
        :type textureAtlas: mcedit2.rendering.textureatlas.TextureAtlas
        :param blocksToShow:
        :type blocksToShow: None or list[basestring or BlockType]
        :return:
        :rtype: BlockListWidget
        """
        super(BlockListWidget, self).__init__()

        load_ui("blocktype_list.ui", baseinstance=self)
        table = self.tableWidget
        columns = ("Block", "Name", "ID", "blockData", "unlocalizedName")

        table.setRowCount(len(blocktypes))
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        for row, block in enumerate(blocktypes):
            icon = QtGui.QIcon(BlockTypePixmap(block, textureAtlas))
            table.setItem(row, 0, QtGui.QTableWidgetItem(icon, block.internalName))
            datas = (None, block.englishName, str(block.ID), str(block.blockData), block.unlocalizedName)

            for i, data in enumerate(datas):
                if data is not None:
                    table.setItem(row, i, QtGui.QTableWidgetItem(data))


def BlockTypePixmap(block, textureAtlas):
    texname = block.textureIconNames[0]
    io = textureAtlas._openImageStream(texname)
    data = io.read()
    array = QtCore.QByteArray(data)
    buf = QtCore.QBuffer(array)
    reader = QtGui.QImageReader(buf)
    image = reader.read()
    pixmap = QtGui.QPixmap.fromImage(image)
    w = pixmap.width()
    h = pixmap.height()
    s = min(w, h)
    if w != h:
        pixmap = pixmap.copy(0, 0, s, s)

    if s != 32:
        pixmap = pixmap.scaledToWidth(32)

    return pixmap
