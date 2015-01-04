
cdef struct ModelQuad:
    float[24] xyzuvc
    char[4] cullface  # isCulled, dx, dy, dz

cdef struct ModelQuadList:
    int count
    ModelQuad *quads

cdef class BlockModels:
    cdef object resourceLoader
    cdef object blocktypes
    cdef object modelBlockJsons
    cdef object modelStateJsons
    cdef object modelQuads
    cdef object _textureNames
    cdef public object firstTextures
    cdef object cookedModels
    cdef ModelQuadList cookedModelsByID[4096][16]
    cdef object cooked
