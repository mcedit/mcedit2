
cdef enum:
    BIOME_NONE = 0
    BIOME_GRASS = 1
    BIOME_FOLIAGE = 2
    BIOME_FOLIAGE_PINE = 3
    BIOME_FOLIAGE_BIRCH = 4
    BIOME_REDSTONE = 5

cdef struct ModelQuad:
    float[32] xyzuvstc
    char[4] cullface  # isCulled, dx, dy, dz
    char[4] quadface  # face, dx, dy, dz
    char biomeTintType

cdef struct ModelQuadList:
    int count
    ModelQuad *quads

cdef class ModelQuadListObj(object):
    cdef ModelQuadList quadList

cdef class BlockModels:
    cdef object resourceLoader
    cdef object blocktypes
    cdef object modelBlockJsons
    cdef object modelStateJsons
    cdef object quadsByResourcePathVariant
    cdef object blockStatesByResourcePathVariant
    cdef object _texturePaths
    cdef public object firstTextures
    cdef object cookedModels
    cdef ModelQuadList cookedModelsByID[4096][16]
    cdef dict cookedModelsByBlockState
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

    cdef cookedModelsForState(self, tuple nameAndState)
