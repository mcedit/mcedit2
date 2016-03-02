# distutils: language = c++
# cython: profile = False, boundscheck=False, initializedcheck=False
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
IF OUTPUT_STATS:
    import time

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

cdef struct RelightChunk:
    # This guy is a big endian array, but Cython only wants to operate on little-endians.
    # We byteswap the entire thing on read, and if we're dirty, byteswap it all out again
    # on write.
    unsigned int[:,:] HeightMap
    # Ditto.
    void * chunk
    char dirty
    

ctypedef unsigned long long section_key_t
ctypedef unsigned long long chunk_key_t

cdef section_key_t section_key(int cx, int cy, int cz):
    # assume 0 < cy < 256
    return (<section_key_t>cx) << 36 | (<section_key_t>cz & 0xFFFFFFF) << 8 | (<section_key_t>cy) & 0xFF

cdef chunk_key_t chunk_key(int cx, int cz):
    return (<chunk_key_t>cx) << 32 | (<section_key_t>cz) & 0xFFFFFFFFLL

DEF CACHE_LIMIT = 100


@cython.final
cdef class RelightCtx(object):
    cdef:
        map[section_key_t, RelightSection] section_cache
        map[chunk_key_t, RelightChunk] chunk_cache
        set[section_key_t] absent_sections
        
        object dimension
        unsigned char [:] brightness
        unsigned char [:] opacity
        IF OUTPUT_STATS:
            unsigned int spreadCount, drawCount, fadeCount
            unsigned int raisedColumns, loweredColumns, columnUpdates
            object startTime
        int _useBlockLight

    def __init__(self, dim):
        self.dimension = dim
        self.brightness = self.dimension.blocktypes.brightness
        self.opacity = self.dimension.blocktypes.opacity
        self._useBlockLight = 1
        IF OUTPUT_STATS:
            self.spreadCount = self.drawCount = self.fadeCount = 0
            self.raisedColumns = self.loweredColumns = self.columnUpdates = 0
            self.startTime = time.time()

    cdef void useBlockLight(self):
        self._useBlockLight = 1

    cdef void useSkyLight(self):
        self._useBlockLight = 0

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

        # Fast exit for absent sections
        if self.absent_sections.find(key) != self.absent_sections.end():
            return NULL

        if not self.dimension.containsChunk(cx, cz):
            return NULL
        chunk = self.dimension.getChunk(cx, cz)
        try:
            section = chunk.getSection(cy, create=True)
        except ValueError:
            self.absent_sections.insert(key)
            return NULL

        if section is None:
            self.absent_sections.insert(key)
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

    # ---
    

    cdef RelightChunk * getChunk(self, int cx, int cz):
        cdef chunk_key_t key = chunk_key(cx, cz)
        cdef map[chunk_key_t, RelightChunk].iterator i = self.chunk_cache.find(key)
        cdef RelightChunk * ret
        if i == self.chunk_cache.end():
            ret = self.cacheChunk(cx, cz)
        else:
            ret = &(deref(i).second)
        return ret

    cdef RelightChunk * cacheChunk(self, int cx, int cz):
        # Initializer is *required* - if memoryview fields are uninitialized, they cannot be assigned
        # later as Cython attempts to decref the uninitialized memoryview and segfaults.
        cdef RelightChunk cachedChunk = [None, NULL, 0]
        cdef long long key = chunk_key(cx, cz)
        if not self.dimension.containsChunk(cx, cz):
            return NULL
        chunk = self.dimension.getChunk(cx, cz)
        if self.chunk_cache.size() > CACHE_LIMIT:
            # xxx decache something!
            pass

        cachedChunk.HeightMap = np.array(chunk.HeightMap, dtype='u4')
        cachedChunk.chunk = <void *>chunk
        Py_INCREF(chunk)

        # weird hack because in Python an assignment is a statement so we cannot write
        # `return self.chunk_cache[key] = cachedChunk` to return a reference to the
        # RelightChunk in the cache...
        cdef RelightChunk * ret
        ret = &self.chunk_cache[key]
        ret[0] = cachedChunk
        return ret
    
    # ---
    
    def __dealloc__(self):
        cdef RelightSection cachedSection
        cdef section_key_t key
        IF OUTPUT_STATS:
            cdef float duration = time.time() - self.startTime
            log.info("RelightCtx Finished: draw=%7d, spread=%7d, fade=%7d, sections=%d "
                     "raisedColumns=%d loweredColumns=%d time=%f",
                     self.drawCount, self.spreadCount, self.fadeCount, self.section_cache.size(),
                     self.raisedColumns, self.loweredColumns, duration)

        for keyval in self.section_cache:
            key = keyval.first
            cachedSection = keyval.second
            cachedSection.Blocks = cachedSection.BlockLight = cachedSection.SkyLight = None
            if cachedSection.dirty:
                (<object>cachedSection.chunk).dirty = True
            Py_DECREF(<object>cachedSection.chunk)
            cachedSection.chunk = NULL

        for ckeyval in self.chunk_cache:
            key = ckeyval.first
            cachedChunk = ckeyval.second
            if cachedChunk.dirty:
                (<object>cachedChunk.chunk).HeightMap[:] = cachedChunk.HeightMap
                (<object>cachedChunk.chunk).dirty = True
            cachedChunk.HeightMap = None
            Py_DECREF(<object>cachedChunk.chunk)
            cachedChunk.chunk = NULL

    # ---

    cdef int getHeightMap(self, int x, int z):
        cdef RelightChunk * chunk = self.getChunk(x >> 4, z >> 4)
        if chunk is NULL:
            return 0
        return chunk.HeightMap[<unsigned int>(z & 0xf),
                               <unsigned int>(x & 0xf)]

    cdef void setHeightMap(self, int x, int z, int value):
        cdef RelightChunk * chunk = self.getChunk(x >> 4, z >> 4)
        if chunk is NULL:
            return
        chunk.dirty = True
        chunk.HeightMap[<unsigned int>(z & 0xf),
                        <unsigned int>(x & 0xf)] = value

    # ---

    cdef char getBlockLight(self, int x, int y, int z):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return 0
        if self._useBlockLight:
            return section.BlockLight[<unsigned int>(y & 0xf),
                                      <unsigned int>(z & 0xf),
                                      <unsigned int>(x & 0xf)]
        else:
            return section.SkyLight[<unsigned int>(y & 0xf),
                                      <unsigned int>(z & 0xf),
                                      <unsigned int>(x & 0xf)]


    cdef void setBlockLight(self, int x, int y, int z, char value):
        cdef RelightSection * section = self.getSection(x >> 4, y >> 4, z >> 4)
        if section is NULL:
            return
        section.dirty = 1
        if self._useBlockLight:
            section.BlockLight[<unsigned int>(y & 0xf),
                               <unsigned int>(z & 0xf),
                               <unsigned int>(x & 0xf)] = value
        else:
            section.SkyLight[<unsigned int>(y & 0xf),
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
        return self.opacity[blockID]

    cdef unsigned char getBlockEffectiveOpacity(self, int x, int y, int z):
        return max(<unsigned char>1, # truncation warning
                   self.getBlockOpacity(x, y, z))

cdef updateSkyLight(RelightCtx ctx,
                     cnp.ndarray[ndim=1, dtype=int] ax,
                     cnp.ndarray[ndim=1, dtype=int] ay,
                     cnp.ndarray[ndim=1, dtype=int] az):
    
    cdef ssize_t i, n
    cdef chunk_key_t k
    cdef int x, y, z, y2, h, oldH, newH, oldLight
    cdef map[chunk_key_t, int] newHeights
    cdef coord c

    cdef deque[coord] litCoords
    cdef deque[coord] dimCoords

    cdef pair[chunk_key_t, int] p

    ctx.useSkyLight()

    # HeightMap stores the block height above the highest opacity>0 block
    #
    # Cache old heightmap values
    n = ax.shape[0]
    for i in range(n):
        x = ax[i]
        z = az[i]
        newHeights[chunk_key(x, z)] = ctx.getHeightMap(x, z)

    # Scan requested coords for changes in height value, store
    # new height values in newHeights
    for i in range(n):
        x = ax[i]
        y = ay[i]
        z = az[i]
        k = chunk_key(x, z)
        h = newHeights[k]
        if y >= h:
            # Block was set above current height - if opaque, increase height
            if ctx.getBlockOpacity(x, y, z):
                newHeights[k] = y + 1
        elif y == h-1:
            # Block was set below current height
            # if it was height-1, and it was set to opacity==0, then drop height
            # until we find an opacity>0 block
            if 0 == ctx.getBlockOpacity(x, y, z):
                for y2 in range(y, -1, -1):
                    if ctx.getBlockOpacity(x, y2, z):
                        newHeights[k] = y2 + 1
                        break

    # Scan newHeights for columns whose height changed, and queue the appropriate
    # lighting updates for columns that shifted up or down.
    for p in newHeights:
        k = p.first
        h = p.second
        x = k >> 32
        z = k & 0xffffffffLL
        oldH = ctx.getHeightMap(x, z)
        c.x = x
        c.z = z
        if h > oldH:
            # Column shifted up - blocks in changed segment reduced light level
            for y2 in range(oldH, h):
                c.y = y2
                dimCoords.push_back(c)
            # Translucent blocks below changed segment also reduced light level
            for y2 in range(oldH, -1, -1):
                c.y = y2
                dimCoords.push_back(c)
                if ctx.getBlockLight(c.x, c.y, c.z) == 0:
                    break
            # Blocks above column may be in a newly created section.
            # This is a shitty, shitty answer. FIXME FIXME FIXME.
            c.y = h
            ctx.setBlockLight(c.x, c.y, c.z, 15)
            litCoords.push_back(c)
            IF OUTPUT_STATS:
                ctx.raisedColumns += 1

        if h < oldH:
            # Column shifted down - blocks in changed segment increased light level
            for y2 in range(h, oldH):
                c.y = y2
                ctx.setBlockLight(c.x, c.y, c.z, 15)
                litCoords.push_back(c)

            IF OUTPUT_STATS:
                ctx.loweredColumns += 1

        if h != oldH:
            # Update chunk height map
            ctx.setHeightMap(x, z, h)

    # Find all blocks below the changed column heights that have themselves changed, and
    # draw light from adjacent chunks.

    for i in range(n):
        x = ax[i]
        y = ay[i]
        z = az[i]
        k = chunk_key(x, z)
        h = newHeights[k]
        if y < h:  # and (x & 0xF == 0)?
            drawLight(ctx, x, y, z)
            spreadLight(ctx, x, y, z)


    #print("Dimming %d, brightening %d" % (dimCoords.size(), litCoords.size()))
    for c in dimCoords:
        oldLight = ctx.getBlockLight(c.x, c.y, c.z)
        ctx.setBlockLight(c.x, c.y, c.z, 0)
        drawLight(ctx, c.x, c.y, c.z)
        fadeLight(ctx, c.x, c.y, c.z, oldLight)

    # lots of repeated work here
    for c in litCoords:
        spreadLight(ctx, c.x, c.y, c.z)

    ctx.useBlockLight()

def updateLightsByCoord(dim, x, y, z):
    if not dim.hasLights:
        return

    x = np.asarray(x, 'i4').ravel()
    y = np.asarray(y, 'i4').ravel()
    z = np.asarray(z, 'i4').ravel()
    cdef cnp.ndarray[ndim=1, dtype=int] ax = x
    cdef cnp.ndarray[ndim=1, dtype=int] ay = y
    cdef cnp.ndarray[ndim=1, dtype=int] az = z
    cdef size_t i


    if not (x.shape == y.shape == z.shape):
        raise ValueError("All coord arrays must be the same size. (No broadcasting.)")

    ctx = RelightCtx(dim)

    if dim.hasSkyLight:
        updateSkyLight(ctx, ax, ay, az)

    for i in range(<size_t>len(ax)):
        updateLights(ctx, ax[i], ay[i], az[i])


def updateLightsInSelection(dim, selection):
    ctx = RelightCtx(dim)
    for x, y, z in selection.positions:
        updateLights(ctx, x, y, z)

cdef void updateLights(RelightCtx ctx, int x, int y, int z):
    cdef char previousLight = ctx.getBlockLight(x, y, z)
    cdef char light
    ctx.setBlockLight(x, y, z, ctx.getBlockBrightness(x, y, z))

    # should be able to often skip this if we can get block's previous opacity in here... bluh
    drawLight(ctx, x, y, z)
    light = ctx.getBlockLight(x, y, z)

    if previousLight < light:
        spreadLight(ctx, x, y, z)

    if previousLight > light:
        fadeLight(ctx, x, y, z, previousLight)

cdef void drawLight(RelightCtx ctx, int x, int y, int z):
    cdef short opacity = ctx.getBlockEffectiveOpacity(x, y, z)
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
        adjacentOpacity = ctx.getBlockEffectiveOpacity(nx, ny, nz)
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
            adjacentOpacity = ctx.getBlockEffectiveOpacity(n_coord.x, n_coord.y, n_coord.z)

            if previousLight - adjacentOpacity <= 0:
                continue

            if previousLight - adjacentOpacity == adjacentLight:
                if foundCells.count(n_coord) == 0:
                    toScan.push_back(toScan_t(n_coord, adjacentLight))
                    foundCells.insert(n_coord)

    return foundCells
