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
    MonsterLocations = "MonsterLocations"
    Items = "Items"
    TileEntities = "TileEntities"
    TileEntityLocations = "TileEntityLocations"
    CommandBlockColors = "CommandBlockColors"
    CommandBlockLocations = "CommandBlockLocations"
    ItemFrames = "ItemFrames"
    TileTicks = "TileTicks"
    TerrainPopulated = "TerrainPopulated"
    ChunkSections = "ChunkSections"
    AllLayers = (Blocks, Entities, Monsters, MonsterLocations, Items,
                 TileEntities, TileEntityLocations,
                 CommandBlockColors, CommandBlockLocations,
                 ItemFrames, TileTicks, ChunkSections)
    DefaultVisibleLayers = (Blocks, Entities, Items, TileEntities, CommandBlockColors, ItemFrames)
