# distutils: language = c++
# cython: profile = True, boundscheck=False, initializedcheck=False
"""
    with_cython
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

# unordered_map was twice as slow, at least with the MSVC 2008 from Python C++ Toolkit
from libcpp.map cimport map
from libcpp.set cimport set
from libcpp.pair cimport pair
from libcpp.deque cimport deque
from libcpp cimport bool

cimport cython
from cython.operator cimport dereference as deref
from cpython cimport Py_INCREF, Py_DECREF

import numpy as np
cimport numpy as cnp

log = logging.getLogger(__name__)

DEF OUTPUT_STATS = False

cdef struct RelightSection:
    unsigned short[:,:,:] Blocks
    unsigned char[:,:,:] BlockLight
    unsigned char[:,:,:] SkyLight
    # To keep the chunk "alive" while we edit its section arrays, we INCREF it and keep it here
    # then DECREF it when the RelightCtx dies and when it gets decached.
    # It must be a <void *> with manual refcounting because Cython won't let me store an <object>
    # in a struct.
    void * chunk
    char dirty

ctypedef long long section_key_t

cdef section_key_t section_key(int cx, int cy, int cz):
    # assume 0 < cy < 256
    return (<section_key_t>cx) << 36 | cz << 8 | cy

DEF CACHE_LIMIT = 100

@cython.final
cdef class RelightCtx(object):
    cdef:
        map[section_key_t, RelightSection] section_cache
        object dimension
        unsigned char [:] brightness
        unsigned char [:] opacity
        IF OUTPUT_STATS:
            unsigned int spreadCount, drawCount, fadeCount

    def __init__(self, dim):
        self.dimension = dim
        self.brightness = self.dimension.blocktypes.brightness
        self.opacity = self.dimension.blocktypes.opacity
        IF OUTPUT_STATS:
            self.spreadCount = self.drawCount = self.fadeCount = 0

    cdef RelightSection * getSection(self, int cx, int cy, int cz):
        cdef section_key_t key = section_key(cx, cy, cz)
        cdef map[section_key_t, RelightSection].iterator i = self.section_cache.find(key)
        cdef RelightSection * ret
        if i == self.section_cache.end():
            ret = self.cacheSection(cx, cy, cz)
        else:
            ret = &(deref(i).second)
        return ret

    cdef RelightSection * cacheSection(self, int cx, int cy, int cz):
        # Initializer is *required* - if memoryview fields are uninitialized, they cannot be assigned
        # later as Cython attempts to decref the uninitialized memoryview and segfaults.
        cdef RelightSection cachedSection = [None, None, None, NULL, 0]
        cdef long long key = section_key(cx, cy, cz)
        if not self.dimension.containsChunk(cx, cz):
            return NULL
        chunk = self.dimension.getChunk(cx, cz)
        section = chunk.getSection(cy)
        if section is None:
            return NULL
        if self.section_cache.size() > CACHE_LIMIT:
            # xxx decache something!
            pass
        assert section.Blocks.shape == section.BlockLight.shape == section.SkyLight.shape == (16, 16, 16)

        cachedSection.Blocks = section.Blocks
        cachedSection.BlockLight = section.BlockLight
        cachedSection.SkyLight = section.SkyLight
        cachedSection.chunk = <void *>chunk
        Py_INCREF(chunk)

        # weird hack because in Python an assignment is a statement so we cannot write
        # `return self.section_cache[key] = cachedSection` to return a reference to the
        # RelightSection in the cache...
        cdef RelightSection * ret
        ret = &self.section_cache[key]
        ret[0] = cachedSection
        return ret

    def __dealloc__(self):
        cdef RelightSection cachedSection
        cdef section_key_t key
        IF OUTPUT_STATS:
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

        return section.BlockLight[<unsigned int>(y & 0xf),
                                  <unsigned int>(z & 0xf),
                                  <unsigned int>(x & 0xf)]

    cdef void setBlockLight(self, int x, int y, int z, char value):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return
        section.dirty = 1
        section.BlockLight[<unsigned int>(y & 0xf),
                           <unsigned int>(z & 0xf),
                           <unsigned int>(x & 0xf)] = value


    cdef unsigned char getBlockBrightness(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 0

        cdef unsigned short blockID = section.Blocks[<unsigned int>(y & 0xf),
                                                     <unsigned int>(z & 0xf),
                                                     <unsigned int>(x & 0xf)]
        cdef char value = self.brightness[blockID]
        return value

    cdef unsigned char getBlockOpacity(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 15

        cdef unsigned short blockID = section.Blocks[<unsigned int>(y & 0xf),
                                                     <unsigned int>(z & 0xf),
                                                     <unsigned int>(x & 0xf)]
        return max(<unsigned char>1, # truncation warning
                   self.opacity[blockID])


def updateLightsByCoord(dim, x, y, z):
    x = np.asarray(x, 'i32').ravel()
    y = np.asarray(y, 'i32').ravel()
    z = np.asarray(z, 'i32').ravel()
    cdef cnp.ndarray[ndim=1, dtype=int] ax = x
    cdef cnp.ndarray[ndim=1, dtype=int] ay = y
    cdef cnp.ndarray[ndim=1, dtype=int] az = z

    if not (x.shape == y.shape == z.shape):
        raise ValueError("All coord arrays must be the same size. (No broadcasting.)")

    ctx = RelightCtx(dim)
    cdef size_t i;

    for i in range(<size_t>len(ax)):
        updateLights(ctx, ax[i], ay[i], az[i])


def updateLightsInSelection(dim, selection):
    ctx = RelightCtx(dim)
    for x, y, z in selection.positions:
        updateLights(ctx, x, y, z)

cdef void updateLights(RelightCtx ctx, int x, int y, int z):
    # import pdb; pdb.set_trace()
    cdef char previousLight = ctx.getBlockLight(x, y, z)
    cdef char light = ctx.getBlockBrightness(x, y, z)
    ctx.setBlockLight(x, y, z, light)

    # should be able to often skip this if we can get block's previous opacity in here... bluh
    drawLight(ctx, x, y, z)

    if previousLight < light:
        spreadLight(ctx, x, y, z)

    if previousLight > light:
        fadeLight(ctx, x, y, z, previousLight)

cdef void drawLight(RelightCtx ctx, int x, int y, int z):
    cdef short opacity = ctx.getBlockOpacity(x, y, z)
    cdef short adjacentLight
    cdef int nx, ny, nz
    IF OUTPUT_STATS:
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
    cdef short light = ctx.getBlockLight(x, y, z)
    if light <= 0:
        return
    IF OUTPUT_STATS:
        ctx.spreadCount += 1

    cdef int nx, ny, nz
    cdef short adjacentLight, adjacentOpacity, newLight

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
        adjacentOpacity = ctx.getBlockOpacity(nx, ny, nz)
        newLight = light - adjacentOpacity
        # If the adjacent cell already has the "correct" light value, stop.
        if newLight > adjacentLight:
            ctx.setBlockLight(nx, ny, nz, <char>newLight)
            spreadLight(ctx, nx, ny, nz)


cdef void fadeLight(RelightCtx ctx, int x, int y, int z, char previousLight):
    IF OUTPUT_STATS:
        ctx.fadeCount += 1
    cdef set[coord] fadedCells = findFadedCells(ctx, x, y, z, previousLight)
    cdef coord this_coord
    for this_coord in fadedCells:
        ctx.setBlockLight(this_coord.x,
                          this_coord.y,
                          this_coord.z,
                          ctx.getBlockBrightness(x, y, z))
        # dim.setBlock(x, y, z, "glass")
    for this_coord in fadedCells:
        drawLight(ctx,
                  this_coord.x,
                  this_coord.y,
                  this_coord.z,
                  )
    for this_coord in fadedCells:
        spreadLight(ctx,
                    this_coord.x,
                    this_coord.y,
                    this_coord.z,
                    )

cdef struct coord:
    int x, y, z

cdef bool coord_operator_less "operator<"(const coord & lhs, const coord & rhs):
    # warning: forcing 'int' to 'bool'
    # cython's temp type for BinOpNode is 'int'
    if lhs.x < rhs.x:
        return True
    elif lhs.x > rhs.x:
        return False
    elif lhs.y < rhs.y:
        return True
    elif lhs.y > rhs.y:
        return False
    elif lhs.z < rhs.z:
        return True
    else:
        return False


ctypedef pair[coord, int] toScan_t

cdef set[coord] findFadedCells(RelightCtx ctx, int x, int y, int z, char previousLight):
    cdef set[coord] foundCells
    cdef deque[toScan_t] toScan
    cdef short adjacentLight, adjacentOpacity
    cdef int i
    cdef coord this_coord, n_coord
    cdef toScan_t this_toScan
    this_coord = [x, y, z]
    toScan.push_back(toScan_t(this_coord, previousLight))

    while 1:
        if toScan.empty():
            break

        this_toScan = toScan.front()
        toScan.pop_front()

        this_coord = this_toScan.first
        x, y, z = this_coord.x, this_coord.y, this_coord.z
        previousLight = this_toScan.second

        for i in range(6):
            if i == 0:
                n_coord.x = x - 1
            elif i == 1:
                n_coord.x = x + 1
            else:
                n_coord.x = x
            if i == 2:
                n_coord.y = y - 1
            elif i == 3:
                n_coord.y = y + 1
            else:
                n_coord.y = y            
            if i == 4:
                n_coord.z = z - 1
            elif i == 5:
                n_coord.z = z + 1
            else:
                n_coord.z = z                

            adjacentLight = ctx.getBlockLight(n_coord.x, n_coord.y, n_coord.z)
            adjacentOpacity = ctx.getBlockOpacity(n_coord.x, n_coord.y, n_coord.z)

            if previousLight - adjacentOpacity <= 0:
                continue

            if previousLight - adjacentOpacity == adjacentLight:
                if foundCells.count(n_coord) == 0:
                    toScan.push_back(toScan_t(n_coord, adjacentLight))
                    foundCells.insert(n_coord)

    return foundCells
