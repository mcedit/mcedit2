"""
   biome_types.py

   Definitions for biome names, climate info, water color, and more.
"""

from collections import namedtuple

_BiomeType = namedtuple("BiomeType", "name temperature rainfall r g b")

class BiomeType(_BiomeType):
    @property
    def watercolor(self):
        return self.r, self.g, self.b

#
# http://github.com/overviewer/Minecraft-Overviewer
# overviewer-core/src/primitives/overlay-biomes.c

biome_types = [
    # 0
    BiomeType("Ocean", 0.5, 0.5, 255, 255, 255),
    BiomeType("Plains", 0.8, 0.4, 255, 255, 255),
    BiomeType("Desert", 2.0, 0.0, 255, 255, 255),
    BiomeType("Extreme Hills", 0.2, 0.3, 255, 255, 255),
    BiomeType("Forest", 0.7, 0.8, 255, 255, 255),
    # 5
    BiomeType("Taiga", 0.05, 0.8, 255, 255, 255),
    BiomeType("Swampland", 0.8, 0.9, 205, 128, 255),
    BiomeType("River", 0.5, 0.5, 255, 255, 255),
    BiomeType("Hell", 2.0, 0.0, 255, 255, 255),
    BiomeType("Sky", 0.5, 0.5, 255, 255, 255),
    # 10
    BiomeType("FrozenOcean", 0.0, 0.5, 255, 255, 255),
    BiomeType("FrozenRiver", 0.0, 0.5, 255, 255, 255),
    BiomeType("Ice Plains", 0.0, 0.5, 255, 255, 255),
    BiomeType("Ice Mountains", 0.0, 0.5, 255, 255, 255),
    BiomeType("MushroomIsland", 0.9, 1.0, 255, 255, 255),
    # 15
    BiomeType("MushroomIslandShore", 0.9, 1.0, 255, 255, 255),
    BiomeType("Beach", 0.8, 0.4, 255, 255, 255),
    BiomeType("DesertHills", 2.0, 0.0, 255, 255, 255),
    BiomeType("ForestHills", 0.7, 0.8, 255, 255, 255),
    BiomeType("TaigaHills", 0.05, 0.8, 255, 255, 255),
    # 20
    BiomeType("Extreme Hills Edge", 0.2, 0.3, 255, 255, 255),
    BiomeType("Jungle", 2.0, 0.45, 255, 255, 255),# <-- GUESS, but a good one
    BiomeType("Jungle Mountains", 2.0, 0.45, 255, 255, 255), # <-- also a guess
]
