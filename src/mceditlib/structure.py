"""
    structure
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from math import floor

from mceditlib import nbt

log = logging.getLogger(__name__)

def exportStructure(filename, dim, selection, author=None, excludedBlocks=None):
    """

    Parameters
    ----------
    filename : unicode
    dim : mceditlib.worldeditor.WorldEditorDimension
    selection : mceditlib.selection.SelectionBox

    Returns
    -------

    """

    excludedBlocks = set(excludedBlocks or [])

    rootTag = nbt.TAG_Compound()
    rootTag['author'] = nbt.TAG_String(author or "Anonymous")
    rootTag['version'] = nbt.TAG_Int(1)
    rootTag['size'] = nbt.TAG_List([nbt.TAG_Int(s) for s in selection.size])
    entities = rootTag['entities'] = nbt.TAG_List(list_type=nbt.ID_COMPOUND)
    blocks = rootTag['blocks'] = nbt.TAG_List(list_type=nbt.ID_COMPOUND)
    palette = rootTag['palette'] = nbt.TAG_List(list_type=nbt.ID_COMPOUND)

    ox, oy, oz = selection.origin

    paletteIDs = {}
    for x, y, z in selection.positions:
        block = dim.getBlock(x, y, z)
        if block in excludedBlocks:
            continue

        paletteIdx = paletteIDs.get(block.nameAndState, None)
        if paletteIdx is None:
            paletteTag = nbt.TAG_Compound()
            paletteTag['Name'] = nbt.TAG_String(block.internalName)
            if len(block.stateDict):
                paletteTag['Properties'] = nbt.TAG_Compound()
                for k, v in block.stateDict.iteritems():
                    paletteTag['Properties'][k] = nbt.TAG_String(v)

            paletteIdx = paletteIDs[block.nameAndState] = len(palette)
            palette.append(paletteTag)

        blockTag = nbt.TAG_Compound()
        blockTag['state'] = nbt.TAG_Int(paletteIdx)
        blockTag['pos'] = nbt.TAG_List([nbt.TAG_Int(a) for a in x - ox, y - oy, z - oz])

        tileEntity = dim.getTileEntity((x, y, z))
        if tileEntity:
            tileEntity = tileEntity.copyWithOffset(-selection.origin)
            blockTag['nbt'] = tileEntity.rootTag
        blocks.append(blockTag)

    for entity in dim.getEntities(selection):
        entity = entity.copyWithOffset(-selection.origin)
        entityTag = nbt.TAG_Compound()
        entityTag['pos'] = nbt.TAG_List([nbt.TAG_Double(a) for a in entity.Position])
        entityTag['blockPos'] = nbt.TAG_List([nbt.TAG_Int(int(floor(a))) for a in entity.Position])
        entityTag['nbt'] = entity.rootTag
        entities.append(entityTag)

    rootTag.save(filename)