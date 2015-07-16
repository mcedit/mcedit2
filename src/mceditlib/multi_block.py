import numpy
from mceditlib import relight
from mceditlib.blocktypes import BlockType
from mceditlib.fakechunklevel import GetBlocksResult

import logging

log = logging.getLogger(__name__)


def chunkPosArray(x, z):
    """
    Construct an array of 8-byte integers made by packing the 4-byte chunk coordinate arrays x and z together.

    :type x: ndarray
    :type z: ndarray
    """
    cx = x >> 4
    cz = z >> 4

    cPos = numpy.zeros(cx.shape, 'i8')
    view = cPos.view('i4')
    view.shape = cx.shape + (2,)
    view[..., 0] = cx
    view[..., 1] = cz

    return cPos

def decodeChunkPos(cPos):
    view = cPos.view('i4')
    view.shape = view.shape[:-1] + (view.shape[-1] / 2, 2)
    return view



def coords_by_chunk(x, y, z):
    """
    Split the x, y, and z coordinate arrays according to chunk location. Return an iterator over tuples of the chunk's
    cx and cz coordinates and arrays of the x y z coordinates located in that chunk.

    Performance note: Implicitly sorts the elements of an intermediate array. May perform better when input arrays are
    short.

    :param x: Array of x coordinates
    :param y: Array of y coordinates
    :param z: Array of z coordinates
    :return: iterator over (cx, cz, x, y, z) tuples, where x, y, and z are arrays and cx and cz are integers
    """

    cPos = chunkPosArray(x, z)
    x = x & 0xf
    z = z & 0xf

    x, y, z = numpy.broadcast_arrays(x, y, z)

    elements, inverse = numpy.unique(cPos, return_inverse=True)
    view = decodeChunkPos(elements)
    cxs, czs = view[..., 0], view[..., 1]

    for index, cx in numpy.ndenumerate(cxs):
        cz = czs[index]

        localMask = inverse == index
        localMask.shape = x.shape
        localX = x[localMask]
        localY = y[localMask]
        localZ = z[localMask]

        yield (cx, cz, localX, localY, localZ, localMask)


def getBlocks(world, x, y, z,
              return_Blocks=True,
              return_Data=False,
              return_BlockLight=False,
              return_SkyLight=False,
              return_Biomes=False):
    """
    High performance method for accessing multiple blocks and their lighting info.

    Requires `world` have a `getChunk(cx, cz)` method
    Requires that method return an object that has a `getBlocks` method that takes the same
    parameters as this one.

    Return the blocks at the requested locations as one or more ndarrays. Returns a
    tuple of ndarrays, one for each `return_` parameter with a True value, in the order
    that the parameters appear. Returns the blocks as raw Block IDs, which you can convert
    to BlockType instances using world.blocktype

    The `x`, `y`, and `z` parameters must have the same shape.

    :param x: Array of x coordinates
    :param y: Array of y coordinates
    :param z: Array of z coordinates
    :param return_Blocks:
    :param return_Data:
    :param return_BlockLight:
    :param return_SkyLight:
    :param return_Biomes:
    :return: GetBlocksResult
    """
    x = numpy.atleast_1d(x)
    y = numpy.atleast_1d(y)
    z = numpy.atleast_1d(z)

    Blocks = Data = BlockLight = SkyLight = Biomes = None
    if return_Blocks:
        Blocks = numpy.zeros(shape=x.shape, dtype='uint16')
    if return_Data:
        Data = numpy.zeros(shape=x.shape, dtype='uint8')
    if return_BlockLight:
        BlockLight = numpy.zeros(shape=x.shape, dtype='uint8')
    if return_SkyLight:
        SkyLight = numpy.zeros(shape=x.shape, dtype='uint8')
    if return_Biomes:
        Biomes = numpy.zeros(shape=x.shape, dtype='uint8')

    result = GetBlocksResult(Blocks, Data, BlockLight, SkyLight, Biomes)

    for cx, cz, x, y, z, mask in coords_by_chunk(x, y, z):
        if not world.containsChunk(cx, cz):
            continue

        chunk = world.getChunk(cx, cz)

        arrays = getChunkBlocks(chunk, x, y, z,
                                return_Blocks,
                                return_Data,
                                return_BlockLight,
                                return_SkyLight,
                                return_Biomes)

        for dest, source in zip(result, arrays):
            if dest is not None and source is not None:
                dest[mask] = source

    return result


def getChunkBlocks(chunk, x, y, z,
                   return_Blocks=True,
                   return_Data=False,
                   return_BlockLight=False,
                   return_SkyLight=False,
                   return_Biomes=False):
    """
    High performance method for accessing multiple blocks and their lighting info.

    Parameters are identical to getBlocks
    :type x: numpy.ndarray
    :type y: numpy.ndarray
    :type z: numpy.ndarray

    """
    Blocks = Data = BlockLight = SkyLight = Biomes = None

    if return_Blocks:
        Blocks = numpy.zeros(x.shape, 'uint16')
    if return_Data:
        Data = numpy.zeros(x.shape, 'uint8')
    if return_BlockLight:
        BlockLight = numpy.zeros(x.shape, 'uint8')
    if return_SkyLight:
        SkyLight = numpy.zeros(x.shape, 'uint8')
    if return_Biomes:
        Biomes = numpy.zeros(x.shape, 'uint8')
        if hasattr(chunk, 'Biomes'):
            Biomes[:] = chunk.Biomes[x, z]

    result = GetBlocksResult(Blocks, Data, BlockLight, SkyLight, Biomes)
    if hasattr(chunk, 'Biomes') and return_Biomes:
        result.Biomes[:] = chunk.Biomes[x, z]

    for cy in chunk.sectionPositions():
        section = chunk.getSection(cy)
        if section is None:
            continue

        sectionMask = (y >> 4) == cy
        if not sectionMask.any():
            continue

        sx = x[sectionMask]
        sy = y[sectionMask]
        sz = z[sectionMask]

        sx &= 0xf
        sy &= 0xf
        sz &= 0xf

        arrays = getSectionBlocks(section, sx, sy, sz,
                                  return_Blocks,
                                  return_Data,
                                  return_BlockLight,
                                  return_SkyLight)

        for dest, src in zip(result, arrays):
            if dest is not None:
                dest[sectionMask] = src



    return result


def getSectionBlocks(section, x, y, z,
                     return_Blocks=True,
                     return_Data=False,
                     return_BlockLight=False,
                     return_SkyLight=False,
):
    """
    Return the blocks at the given positions. Returns a list of one or more arrays depending on which `return_*`
    parameters were passed.

    x, y, z must be in the range 0..15
    """
    return_arrays = []
    if return_Blocks and hasattr(section, 'Blocks'):
        return_arrays.append(section.Blocks[y, z, x])
    else:
        return_arrays.append(None)
    if return_Data and hasattr(section, 'Data'):
        return_arrays.append(section.Data[y, z, x])
    else:
        return_arrays.append(None)
    if return_BlockLight and hasattr(section, 'BlockLight'):
        return_arrays.append(section.BlockLight[y, z, x])
    else:
        return_arrays.append(None)
    if return_SkyLight and hasattr(section, 'SkyLight'):
        return_arrays.append(section.SkyLight[y, z, x])
    else:
        return_arrays.append(None)

    return return_arrays

def maskArray(array, mask):
    if array is None:
        return None
    if array.shape == (1,):
        return array
    else:
        return array[mask]

def atleast_3d(ary):
    """
    numpy.atleast_3d adds axes on either side of a 1d array's axis, but I want the new axes to come afterward.
    :param ary:
    :type ary:
    :return:
    :rtype:
    """
    ary = numpy.asanyarray(ary)
    if len(ary.shape) == 0:
        result = ary.reshape(1, 1, 1)
    elif len(ary.shape) == 1:
        result = ary[:, None, None]
    elif len(ary.shape) == 2:
        result = ary[:,:, None]
    else:
        result = ary

    return result

def setBlocks(dimension, x, y, z,
              Blocks=None,
              Data=None,  # Deprecate soon
              BlockLight=None,
              SkyLight=None,
              Biomes=None,
              updateLights=True):
    """
    Change the blocks at the given positions. All parameters must be arrays of the same shape, or single values.

    :type dimension: mceditlib.worldeditor.WorldEditorDimension
    """
    x = atleast_3d(x)
    y = atleast_3d(y)
    z = atleast_3d(z)
    if Blocks is not None:
        if isinstance(Blocks, (BlockType, basestring)):
            Blocks = [Blocks]
        _Blocks = []
        _Data = []
        if isinstance(Blocks, int):
            Blocks = [Blocks]


        for block in Blocks:
            if isinstance(block, basestring):
                block = dimension.blocktypes[block]
            if isinstance(block, BlockType):
                _Blocks.append(block.ID)
                _Data.append(block.meta)
            else:
                _Blocks.append(block)
        if len(_Blocks):
            Blocks = _Blocks
        if len(_Data):
            Data = _Data

    if Blocks is None and Data is None:
        updateLights = False


    Blocks = atleast_3d(Blocks) if Blocks is not None else None
    Data = atleast_3d(Data) if Data is not None else None
    BlockLight = atleast_3d(BlockLight) if BlockLight is not None else None
    SkyLight = atleast_3d(SkyLight) if SkyLight is not None else None
    Biomes = atleast_3d(Biomes) if Biomes is not None else None

    arrays_to_broadcast = [x, y, z]

    if Blocks is not None:
        arrays_to_broadcast.append(Blocks)
    if Data is not None:
        arrays_to_broadcast.append(Data)
    if BlockLight is not None:
        arrays_to_broadcast.append(BlockLight)
    if SkyLight is not None:
        arrays_to_broadcast.append(SkyLight)
    if Biomes is not None:
        arrays_to_broadcast.append(Biomes)

    if any(a.size == 0 for a in (x, y, z)):
        return

    broadcasted_arrays = numpy.broadcast_arrays(*arrays_to_broadcast)

    x, y, z = broadcasted_arrays[:3]
    broadcasted_arrays = broadcasted_arrays[3:]


    if Blocks is not None:
        Blocks, broadcasted_arrays = broadcasted_arrays[0], broadcasted_arrays[1:]
    if Data is not None:
        Data, broadcasted_arrays = broadcasted_arrays[0], broadcasted_arrays[1:]
    if BlockLight is not None:
        BlockLight, broadcasted_arrays = broadcasted_arrays[0], broadcasted_arrays[1:]
    if SkyLight is not None:
        SkyLight, broadcasted_arrays = broadcasted_arrays[0], broadcasted_arrays[1:]
    if Biomes is not None:
        Biomes, broadcasted_arrays = broadcasted_arrays[0], broadcasted_arrays[1:]


    for cx, cz, sx, sy, sz, mask in coords_by_chunk(x, y, z):
        chunk = dimension.getChunk(cx, cz, create=True)
        if chunk is None:
            continue
        setChunkBlocks(chunk, sx, sy, sz,
                       maskArray(Blocks, mask),
                       maskArray(Data, mask),
                       maskArray(BlockLight, mask),
                       maskArray(SkyLight, mask),
                       maskArray(Biomes, mask))
        chunk.dirty = True

    if updateLights:
        relight.updateLightsByCoord(dimension, x, y, z)


def setChunkBlocks(chunk, x, y, z,
                   Blocks=None,
                   Data=None,
                   BlockLight=None,
                   SkyLight=None,
                   Biomes=None,
):
    """
    Change the blocks at the given positions. All parameters must be arrays of the same shape, or single values.
    Chunk must have a `world` attribute and `getSection` function.
    """

    for cy in chunk.sectionPositions():
        section = chunk.getSection(cy)
        if section is None:
            continue

        sectionMask = (y >> 4 == cy)

        sx = x[sectionMask]
        if not len(sx):
            continue

        sy = y[sectionMask]
        sz = z[sectionMask]
        sx &= 0xf
        sy &= 0xf
        sz &= 0xf

        setSectionBlocks(section, sx, sy, sz,
                         maskArray(Blocks, sectionMask),
                         maskArray(Data, sectionMask),
                         maskArray(BlockLight, sectionMask),
                         maskArray(SkyLight, sectionMask))

    if Biomes is not None and hasattr(chunk, 'Biomes'):
        chunk.Biomes[x & 0xf, z & 0xf] = Biomes



def setSectionBlocks(section, x, y, z,
                     Blocks=None,
                     Data=None,
                     BlockLight=None,
                     SkyLight=None,
):
    """
    Change the blocks at the given positions. All parameters must be arrays of the same shape, or single values.

    x, y, z must be in the range 0..15
    """
    if Blocks is not None:
        section.Blocks[y, z, x] = Blocks
    if Data is not None:
        section.Data[y, z, x] = Data
    if BlockLight is not None:
        section.BlockLight[y, z, x] = BlockLight
    if SkyLight is not None:
        section.SkyLight[y, z, x] = SkyLight

