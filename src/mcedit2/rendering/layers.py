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
    HeightMap = "HeightMap"
    MobSpawns = "Places Where Creepers Can Spawn"
    ChunkSections = "ChunkSections"
    AllLayers = (Blocks, MonsterLocations, Items,
                 TileEntities, TileEntityLocations,
                 CommandBlockColors, CommandBlockLocations,
                 ItemFrames, TileTicks, ChunkSections, HeightMap,
                 MobSpawns)
    DefaultVisibleLayers = (Blocks, Items, TileEntities, CommandBlockColors, ItemFrames)
