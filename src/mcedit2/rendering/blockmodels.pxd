
cdef enum:
    BIOME_NONE = 0
    BIOME_GRASS = 1
    BIOME_FOLIAGE = 2

cdef struct ModelQuad:
    float[32] xyzuvstc
    char[4] cullface  # isCulled, dx, dy, dz
    char[4] quadface  # face, dx, dy, dz
    char biomeTintType

cdef struct ModelQuadList:
    int count
    ModelQuad *quads

cdef class BlockModels:
    cdef object resourceLoader
    cdef object blocktypes
    cdef object modelBlockJsons
    cdef object modelStateJsons
    cdef object modelQuads
    cdef object _texturePaths
    cdef public object firstTextures
    cdef object cookedModels
    cdef ModelQuadList cookedModelsByID[4096][16]
    cdef object cooked

    cdef object grassImage
    cdef unsigned int grassImageX
    cdef unsigned int grassImageY
    cdef object _grassImageBits
    cdef unsigned char[:] grassImageBits

    cdef object foliageImage
    cdef unsigned int foliageImageX
    cdef unsigned int foliageImageY
    cdef object _foliageImageBits
    cdef unsigned char[:] foliageImageBits

    cdef ModelQuadList fluidQuads[9]
