from mceditlib.anvil.adapter import SessionLockLost
from mceditlib.worldeditor import WorldEditor
import pytest

def test_session_lock(pc_world):
    level2 = WorldEditor(pc_world.filename, resume=False)
    with pytest.raises(SessionLockLost):
        pc_world.saveChanges()

