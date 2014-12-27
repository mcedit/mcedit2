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
    TileTicks = "TileTicks"
    TerrainPopulated = "TerrainPopulated"
    AllLayers = (Blocks, Entities, Monsters, Items, TileEntities, TileTicks)
