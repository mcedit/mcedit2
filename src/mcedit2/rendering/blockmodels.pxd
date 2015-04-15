
cdef struct ModelQuad:
    float[32] xyzuvstc
    char[4] cullface  # isCulled, dx, dy, dz
    char[4] quadface  # face, dx, dy, dz

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

    cdef ModelQuadList fluidQuads[9]
