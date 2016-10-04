"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
from mceditlib import nbt

log = logging.getLogger(__name__)

#
# def loadWorld(name):
#     """
#     Convenience function to load the named world from the
#     default Minecraft save file directory (defined in directories.py).
#
#     :rtype: LevelBase
#     """
#     from mceditlib.directories import saveFileDir
#     filename = os.path.join(saveFileDir, name)
#     return WorldEditor(filename)

class UnknownFormatError(ValueError):
    """
    Raised by findAdapter if no adapter was found.
    """

def findAdapter(filename, readonly=False, resume=None, getInfo=False):
    """
    Try to identify the given file and find an adapter that will open it.
    Returns an Adapter object if a class is found, and raises ValueError if
    no classes were able to open it.

    Knows about ZipSchematic, PocketWorldAdapter, WorldEditor, JavaLevel,
    IndevLevel, SchematicFile, and INVEditChest

    If getInfo is True, returns a WorldInfo object that contains at least
    the world's readable name and Minecraft version.

    :param filename: The file to open
    :type filename: string
    """
    # from mceditlib.indev import IndevLevel
    from mceditlib.anvil.adapter import AnvilWorldAdapter
    # from mceditlib.java import JavaLevel
    # from mceditlib.pocket import PocketWorldAdapter
    from mceditlib.schematic import SchematicFileAdapter

    if not os.path.exists(filename):
        raise IOError("File not found: %s" % filename)

    log.debug(u"Identifying %s", filename)

    classes = [AnvilWorldAdapter, SchematicFileAdapter]
    for cls in classes:
        log.debug("%s: Attempting", cls.__name__)
        if isLevel(cls, filename):
            log.debug("%s: Opening", cls.__name__)
            if getInfo:
                level = cls.getWorldInfo(filename)
            else:
                level = cls(filename=filename, readonly=readonly, resume=resume)
            log.debug("%s: Opened%s", cls.__name__, " read-only" if readonly else "")
            return level

    raise UnknownFormatError("Cannot detect type of file %s." % filename)


def isLevel(cls, filename):
    """
    Return True if the given level adapter can load the given filename, False otherwise.
    Tries to call cls.canOpenFile on the filename, then
    cls._isDataLevel on the file's data, then cls._isTagLevel on an NBT tree
    loaded from that data. If none of these methods are present, return False.

    Subclasses should implement one of canOpenFile, _isDataLevel, or _isTagLevel.
    """
    if hasattr(cls, "canOpenFile"):
        return cls.canOpenFile(filename)

    if os.path.isfile(filename):
        with open(filename, "rb") as f:
            data = f.read()

        if hasattr(cls, "_isDataLevel"):
            return cls._isDataLevel(data)

        if hasattr(cls, "_isTagLevel"):
            try:
                rootTag = nbt.load(filename, data)
            except:
                return False

            return cls._isTagLevel(rootTag)

    return False
