'''
    Generic, half-complete support for Minecraft Classic levels as raw block arrays
    offset into the file by an automatically detected amount. Also reads dimensions
    from numbers in the file name.

    Needs java serialization support (preferably using a java sub-program) for full
    Classic support.
'''
from __future__ import absolute_import

from cStringIO import StringIO
import gzip
from logging import getLogger
import os
import re

from numpy import fromstring

from mceditlib import blocktypes
from mceditlib.fakechunklevel import FakeChunkedLevelAdapter

log = getLogger(__name__)

class JavaLevel(FakeChunkedLevelAdapter):
    blocktypes = blocktypes.classic_blocktypes

    def setBlockData(self, *args):
        pass

    def getBlockData(self, *args):
        return 0

    @property
    def Height(self):
        return self.Blocks.shape[2]

    @property
    def Length(self):
        return self.Blocks.shape[1]

    @property
    def Width(self):
        return self.Blocks.shape[0]

    def guessSize(self, data):
        Width = 64
        Length = 64
        Height = 64
        if data.shape[0] <= (32 * 32 * 64) * 2:
            log.warn(u"Can't guess the size of a {0} byte level".format(data.shape[0]))
            raise IOError("JavaLevel attempted for smaller than 64 blocks cubed")
        if data.shape[0] > (64 * 64 * 64) * 2:
            Width = 128
            Length = 128
            Height = 64
        if data.shape[0] > (128 * 128 * 64) * 2:
            Width = 256
            Length = 256
            Height = 64
        if data.shape[0] > (256 * 256 * 64) * 2:  # could also be 256*256*256
            Width = 512
            Length = 512
            Height = 64
        if data.shape[0] > 512 * 512 * 64 * 2:  # just to load shadowmarch castle
            Width = 512
            Length = 512
            Height = 256
        return Width, Length, Height

    @classmethod
    def _isDataLevel(cls, data):
        try:
            gz = gzip.GzipFile(fileobj=StringIO(data))
            magic = [ord(i) for i in gz.read(4)]
        except Exception:
            return False

        return (magic[0] == 0x27 and
                magic[1] == 0x1B and
                magic[2] == 0xb7 and
                magic[3] == 0x88)

    def __init__(self, filename, shape=None):

        self.filename = filename
        try:
            gz = gzip.GzipFile(filename)
            strdata = gz.read()
        except Exception:
            strdata = open(filename, "rb").read()

        data = fromstring(strdata, dtype='uint8')

        self.filedata = data

        if shape is None:
            # try to take x,z,y from the filename
            r = re.findall("\d+", os.path.basename(filename))
            if r and len(r) >= 3:
                (w, l, h) = map(int, r[-3:])
                if w * l * h > data.shape[0]:
                    log.info("Not enough blocks for size " + str((w, l, h)))
                    w, l, h = self.guessSize(data)
            else:
                w, l, h = self.guessSize(data)
        else:
            w, h, l = shape

        log.info(u"JavaLevel created for potential level of size " + str((w, l, h)))

        blockCount = h * l * w
        if blockCount > data.shape[0]:
            raise ValueError("Level file does not contain enough blocks! (size {s}) Try putting the size into the filename, e.g. server_level_{w}_{l}_{h}.dat".format(w=w, l=l, h=h, s=data.shape))

        blockOffset = data.shape[0] - blockCount
        blocks = data[blockOffset:blockOffset + blockCount]

        maxBlockType = 64  # maximum allowed in classic
        while max(blocks[-4096:]) > maxBlockType:
            # guess the block array by starting at the end of the file
            # and sliding the blockCount-sized window back until it
            # looks like every block has a valid blockNumber
            blockOffset -= 1
            blocks = data[blockOffset:blockOffset + blockCount]

            if blockOffset <= -data.shape[0]:
                raise IOError("Can't find a valid array of blocks <= #%d" % maxBlockType)

        self.Blocks = blocks
        self.blockOffset = blockOffset
        blocks.shape = (w, l, h)
        blocks.strides = (1, w, w * l)

    def save(self):
        s = StringIO()
        g = gzip.GzipFile(fileobj=s, mode='wb')

        g.write(self.filedata.tostring())
        g.flush()
        g.close()

        with open(self.filename + ".tmp", 'wb') as f:
            f.write(s.getvalue())

        os.remove(self.filename)
        os.rename(self.filename + ".tmp", self.filename)

__all__ = ["JavaLevel"]
