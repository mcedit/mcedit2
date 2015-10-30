"""
    revisionhistory_test
"""
from mceditlib.revisionhistory import RevisionHistory

import logging

log = logging.getLogger(__name__)

from .conftest import copy_temp_file

import pytest

from mceditlib import nbt


@pytest.fixture
def history(tmpdir):
    filename = "AnvilWorld"
    tmpname = copy_temp_file(tmpdir, filename)
    return RevisionHistory(tmpname.strpath)


def readChunkTag(rev, cx, cz):
    return nbt.load(buf=rev.readChunkBytes(cx, cz, ""))


def writeChunkTag(rev, cx, cz, tag):
    return rev.writeChunkBytes(cx, cz, "", tag.save(compressed=False))


def testRevision(history):
    revA = history.createRevision()
    log.info("revA")
    # rev A @1 - touch chunk 1
    cx, cz = iter(revA.chunkPositions("")).next()
    chunk = readChunkTag(revA, cx, cz)

    old_tag = tag = nbt.load(buf=history.rootFolder.readChunkBytes(cx, cz, ""))

    assert readChunkTag(history.rootNode, cx, cz) == tag
    assert chunk == tag
    chunk["Level"]["test"] = nbt.TAG_String("test string")

    writeChunkTag(revA, cx, cz, chunk)

    tag = readChunkTag(revA, cx, cz)
    assert "test" in tag["Level"] and tag["Level"]["test"].value == "test string"

    revB = history.createRevision()
    log.info("revB")

    # rev B @2 - delete chunk 2
    tag = readChunkTag(revB, cx, cz)
    assert "test" in tag["Level"] and tag["Level"]["test"].value == "test string"

    revB.deleteChunk(cx+1, cz, "")
    assert not revB.containsChunk(cx+1, cz, "")

    revC = history.createRevision()
    log.info("revC")

    # rev C @3 - delete file
    assert not revC.containsChunk(cx+1, cz, "")
    revC.deleteFile("level.dat")

    assert not revC.containsFile("level.dat")

    changes = revC.getChanges()
    assert changes.chunks[""] == set()
    assert changes.files == {"level.dat"}

    tailRev = history.getRevision(0)

    history.writeAllChanges()

    # initial folder (rev idx 0) and following nodes replaced by reverse nodes
    # rev C @3 replaced by initial folder
    assert revC.invalid

    revC = history.getHead()
    assert tailRev is revC

    changes = revC.getChanges()
    assert changes.chunks[""] == set()
    assert changes.files == {"level.dat"}

    # rev D - create chunk 3
    revD = history.createRevision()
    log.info("revD")

    assert not revD.containsFile("level.dat")
    writeChunkTag(revD, 1000, 1000, old_tag)

    assert not history.rootFolder.containsFile("level.dat")
    assert not history.rootFolder.containsChunk(cx+1, cz, "")

    assert "test" in tag["Level"]
    tag = readChunkTag(history.rootFolder, cx, cz)
    assert tag != old_tag
    assert "test" in tag["Level"]

    # grab rev B
    revBagain = history.getRevision(2)
    assert "test" in readChunkTag(revBagain, cx, cz)["Level"]
    assert not revBagain.containsChunk(cx+1, cz, "")

    # rev B should be read only
    with pytest.raises(IOError):
        writeChunkTag(revBagain, cx, cz, old_tag)

    # check all changes so far
    allChanges = history.getRevisionChanges(0, revD)
    assert allChanges.chunks[""] == {(cx, cz), (cx+1, cz), (1000, 1000)}
    assert allChanges.files == {"level.dat"}

    # insert rev E after rev B
    # world folder is now at the end of an orphan chain at rev @2
    # orphaned revisions are read only and still valid, but do not appear in the history
    revE = history.createRevision(2)
    assert "test" in readChunkTag(revE, cx, cz)["Level"]
    assert not revE.containsChunk(cx+1, cz, "")

    history.close()


