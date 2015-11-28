"""
    blocktype_list
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui, QtCore
import logging
from mcedit2.resourceloader import ResourceNotFound
from mcedit2.ui.blocktype_list import Ui_blocktypeList

log = logging.getLogger(__name__)

class BlockListWidget(QtGui.QWidget, Ui_blocktypeList):
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
        self.setupUi(self)

        table = self.tableWidget
        columns = ("Block", "Name", "ID", "blockData", "unlocalizedName")

        table.setRowCount(len(blocktypes))
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        for row, block in enumerate(blocktypes):
            icon = QtGui.QIcon(BlockTypePixmap(block, textureAtlas))
            table.setItem(row, 0, QtGui.QTableWidgetItem(icon, block.internalName + block.blockState))
            datas = (None, block.displayName, str(block.ID), str(block.meta), block.internalName + block.blockState)

            for i, data in enumerate(datas):
                if data is not None:
                    table.setItem(row, i, QtGui.QTableWidgetItem(data))


def BlockTypePixmap(block, textureAtlas, size=32):
    """

    :param block:
    :type block: mceditlib.blocktypes.BlockType
    :param textureAtlas:
    :type textureAtlas: mcedit2.rendering.textureatlas.TextureAtlas
    :return:
    :rtype: QtGui.QPixmap
    """
    models = textureAtlas.blockModels
    texname = models.firstTextures.get(block.internalName + block.blockState)
    if texname is None:
        log.debug("No texture for %s!", block.internalName + block.blockState)
        texname = "MCEDIT_UNKNOWN"
    try:
        io = textureAtlas._openImageStream(texname)
        return TexturePixmap(io, size=size, texname=texname)
    except (ValueError, ResourceNotFound) as e:
        log.warn("BlockTypePixmap: Failed to read texture %s: %r", texname, e)


def TexturePixmap(io, size=32, texname="Not provided"):
    try:
        data = io.read()
        array = QtCore.QByteArray(data)
        buf = QtCore.QBuffer(array)
        reader = QtGui.QImageReader(buf)
        image = reader.read()
        pixmap = QtGui.QPixmap.fromImage(image)
        if pixmap.isNull():
            log.warn("File %s produced a null pixmap", texname)
            return None

        w = pixmap.width()
        h = pixmap.height()
        s = min(w, h)
        if w != h:
            pixmap = pixmap.copy(0, 0, s, s)

        if s != size:
            pixmap = pixmap.scaledToWidth(size)

        return pixmap
    except ValueError as e:
        log.warn("TexturePixmap: Failed to load texture %s: %r", texname, e)
