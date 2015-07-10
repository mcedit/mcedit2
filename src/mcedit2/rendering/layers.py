"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
log = logging.getLogger(__name__)

class Layer:
    Blocks = "Blocks"
    Entities = "Entities"
    Monsters = "Monsters"
    Items = "Items"
    TileEntities = "TileEntities"
    ItemFrames = "ItemFrames"
    TileTicks = "TileTicks"
    TerrainPopulated = "TerrainPopulated"
    ChunkSections = "ChunkSections"
    AllLayers = (Blocks, Entities, Items, TileEntities, ItemFrames, TileTicks, ChunkSections)
    DefaultVisibleLayers = (Blocks, Entities, Items, TileEntities, ItemFrames)
