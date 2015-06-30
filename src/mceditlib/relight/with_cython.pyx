# distutils: language = c++
# cython: profile = True
"""
    with_cython
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from libcpp.map cimport map
cimport numpy as cnp

from cpython cimport Py_INCREF, Py_DECREF
from libc.stdlib cimport malloc, free

log = logging.getLogger(__name__)

OUTPUT_STATS = True

cdef struct RelightSection:
    unsigned short[:,:,:] Blocks
    unsigned char[:,:,:] BlockLight
    unsigned char[:,:,:] SkyLight
    # To keep the chunk "alive" while we edit its section arrays, we INCREF it and keep it here
    # then DECREF it when the RelightCtxd dies and when it gets decached.
    # It must be a <void *> with manual refcounting because Cython won't let me store an <object>
    # in a struct.
    void * chunk
    char dirty

ctypedef long long section_key_t

cdef section_key_t section_key(int cx, int cy, int cz):
    # assume 0 < cy < 256
    return (<section_key_t>cx) << 36 | cz << 8 | cy

DEF CACHE_LIMIT = 100

cdef class RelightCtx(object):
    cdef:
        map[section_key_t, RelightSection] section_cache
        object dimension
        char [:] brightness
        char [:] opacity
        unsigned int spreadCount, drawCount, fadeCount

    def __init__(self, dim):
        self.dimension = dim
        self.brightness = self.dimension.blocktypes.brightness
        self.opacity = self.dimension.blocktypes.opacity
        self.spreadCount = self.drawCount = self.fadeCount = 0

    cdef RelightSection * getSection(self, int cx, int cy, int cz):
        cdef long long key = section_key(cx, cy, cz)
        cdef map[long long, RelightSection].iterator i = self.section_cache.find(key)

        # Initializer is *required* - if memoryview fields are uninitialized, they cannot be assigned
        # later as Cython attempts to decref the uninitialized memoryview and segfaults.
        cdef RelightSection cachedSection = [None, None, None, NULL, 0]

        if i == self.section_cache.end():
            if not self.dimension.containsChunk(cx, cz):
                return NULL
            chunk = self.dimension.getChunk(cx, cz)
            section = chunk.getSection(cy)
            if section is None:
                return NULL
            if self.section_cache.size() > CACHE_LIMIT:
                # xxx decache something!
                pass
            cachedSection.Blocks = section.Blocks
            cachedSection.BlockLight = section.BlockLight
            cachedSection.SkyLight = section.SkyLight
            cachedSection.chunk = <void *>chunk
            Py_INCREF(chunk)
            self.section_cache[key] = cachedSection

        return &(self.section_cache[key])

    def __dealloc__(self):
        cdef RelightSection cachedSection
        cdef section_key_t key
        if OUTPUT_STATS:
            print("RelightCtx Finished: draw=%7d, spread=%7d, fade=%7d" % (self.drawCount, self.spreadCount, self.fadeCount))
        for keyval in self.section_cache:
            key = keyval.first
            cachedSection = keyval.second
            cachedSection.Blocks = cachedSection.BlockLight = cachedSection.SkyLight = None
            if cachedSection.dirty:
                (<object>cachedSection.chunk).dirty = True
            Py_DECREF(<object>cachedSection.chunk)
            cachedSection.chunk = NULL

    cdef char getBlockLight(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 0

        return section.BlockLight[y & 0xf, z & 0xf, x & 0xf]

    cdef void setBlockLight(self, int x, int y, int z, char value):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return
        section.dirty = 1
        section.BlockLight[y & 0xf, z & 0xf, x & 0xf] = value


    cdef char getBlockBrightness(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 0

        cdef unsigned short blockID = section.Blocks[y & 0xf, z & 0xf, x & 0xf]
        cdef char value = self.brightness[blockID]
        return value

    cdef char getBlockOpacity(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 15

        cdef unsigned short blockID = section.Blocks[y & 0xf, z & 0xf, x & 0xf]
        return max(<char>1, # truncation warning
                   self.opacity[blockID])


def updateLightsByCoord(dim, x, y, z):
    ctx = RelightCtx(dim)
    for i in range(len(x)):
        updateLights(ctx, x[i], y[i], z[i])

def updateLightsInSelection(dim, selection):
    ctx = RelightCtx(dim)
    for x, y, z in selection.positions:
        updateLights(ctx, x, y, z)

cdef void updateLights(RelightCtx ctx, int x, int y, int z):
    # import pdb; pdb.set_trace()
    cdef char previousLight = ctx.getBlockLight(x, y, z)
    cdef char light = ctx.getBlockBrightness(x, y, z)
    ctx.setBlockLight(x, y, z, light)

    drawLight(ctx, x, y, z)

    if previousLight < light:
        spreadLight(ctx, x, y, z)

    if previousLight > light:
        fadeLight(ctx, x, y, z, previousLight)

cdef void drawLight(RelightCtx ctx, int x, int y, int z):
    cdef char opacity = ctx.getBlockOpacity(x, y, z)
    cdef char adjacentLight
    cdef int nx, ny, nz
    ctx.drawCount += 1
    cdef int i
    for i in range(6):
        if i == 0:
            nx = x - 1
        elif i == 1:
            nx = x + 1
        else:
            nx = x
        if i == 2:
            ny = y - 1
        elif i == 3:
            ny = y + 1
        else:
            ny = y
        if i == 4:
            nz = z - 1
        elif i == 5:
            nz = z + 1
        else:
            nz = z

        adjacentLight = ctx.getBlockLight(nx, ny, nz)
        if adjacentLight - opacity > ctx.getBlockLight(x, y, z):
            ctx.setBlockLight(x, y, z, adjacentLight - opacity)

cdef void spreadLight(RelightCtx ctx, int x, int y, int z):
    cdef char light = ctx.getBlockLight(x, y, z)
    if light <= 0:
        return
    ctx.spreadCount += 1

    cdef int nx, ny, nz
    cdef char adjacentLight, adjacentOpacity, newLight

    cdef int i
    for i in range(6):
        if i == 0:
            nx = x - 1
        elif i == 1:
            nx = x + 1
        else:
            nx = x
        if i == 2:
            ny = y - 1
        elif i == 3:
            ny = y + 1
        else:
            ny = y
        if i == 4:
            nz = z - 1
        elif i == 5:
            nz = z + 1
        else:
            nz = z

        # xxx cast to int because one of these is a numpy.uint8 and
        # light - opacity rolls over to a large number.
        adjacentLight = int(ctx.getBlockLight(nx, ny, nz))
        adjacentOpacity = ctx.getBlockOpacity(nx, ny, nz)
        newLight = light - adjacentOpacity
        # If the adjacent cell already has the "correct" light value, stop.
        if newLight > adjacentLight:
            ctx.setBlockLight(nx, ny, nz, newLight)
            spreadLight(ctx, nx, ny, nz)


cdef void fadeLight(RelightCtx ctx, int x, int y, int z, char previousLight):
    ctx.fadeCount += 1
    fadedCells = findFadedCells(ctx, x, y, z, previousLight)
    for x, y, z in fadedCells:
        ctx.setBlockLight(x, y, z, ctx.getBlockBrightness(x, y, z))
        # dim.setBlock(x, y, z, "glass")
    for x, y, z in fadedCells:
        drawLight(ctx, x, y, z)
    for x, y, z in fadedCells:
        spreadLight(ctx, x, y, z)


def relCoords(int ox, int oy, int oz, coords):
    # for debugging
    for x, y, z, l in coords:
        yield x - ox, y - oy, z - oz


cdef findFadedCells(RelightCtx ctx, int x, int y, int z, char previousLight):
    foundCells = set()
    toScan = [(x, y, z, previousLight)]
    cdef char adjacentLight, adjacentOpacity
    cdef int nx, ny, nz
    cdef int i

    while len(toScan):

        x, y, z, previousLight = toScan.pop(0)
        for i in range(6):
            if i == 0:
                nx = x - 1
            elif i == 1:
                nx = x + 1
            else:
                nx = x
            if i == 2:
                ny = y - 1
            elif i == 3:
                ny = y + 1
            else:
                ny = y            
            if i == 4:
                nz = z - 1
            elif i == 5:
                nz = z + 1
            else:
                nz = z                

            adjacentLight = int(ctx.getBlockLight(nx, ny, nz))
            adjacentOpacity = ctx.getBlockOpacity(nx, ny, nz)
            if previousLight - adjacentOpacity <= 0:
                continue
            if previousLight - adjacentOpacity == adjacentLight:
                if (nx, ny, nz) not in foundCells:
                    toScan.append((nx, ny, nz, adjacentLight))
                    foundCells.add((nx, ny, nz))

    return foundCells
