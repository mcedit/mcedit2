"""
   biome_types.py

   Definitions for biome names, climate info, water color, and more.
"""

from collections import namedtuple
import pkg_resources
import csv

_BiomeType = namedtuple("BiomeType", "ID name temperature rainfall")

class BiomeType(_BiomeType):
    pass


class BiomeTypes(object):
    def __init__(self):
        self.types = {}

        io = pkg_resources.resource_stream(__name__, "biomes.csv")
        c = csv.reader(io)
        for record in c:
            if record[0] == "ID":
                # headers: ID,Name,Temperature,Rainfall
                continue

            ID, name, temp, rain = record[:4]
            self.types[int(ID)] = BiomeType(int(ID), name, float(temp), float(rain))

