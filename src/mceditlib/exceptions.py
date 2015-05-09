from __future__ import absolute_import

class PlayerNotFound(KeyError):
    """ Requested player not found in level.
    """


class ChunkNotPresent(KeyError):
    """ Requested chunk not found in level.
    """


class ChunkSizeError(ValueError):
    """ Attempted to save a chunk larger than region file's allocation limit (1 MB)
    """


class LevelFormatError(Exception):
    """ General error for level data not being formatted as expected
    """

class RegionFormatError(LevelFormatError):
    """ Region index entry points outside of the file or to an incomplete sector. Region compress type
    is unknown.
    """
    pass

class ChunkFormatError(LevelFormatError):
    """ Chunk did not have an expected NBT tag.
    """
    pass







