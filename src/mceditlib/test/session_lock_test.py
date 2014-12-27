from mceditlib.anvil.adapter import SessionLockLost
from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel
import unittest

class SessionLockTest(unittest.TestCase):
    def test_session_lock(self):
        temp = TempLevel("AnvilWorld")
        level = temp
        level2 = WorldEditor(level.filename, resume=False)
        def touch():
            level.saveChanges()
        self.assertRaises(SessionLockLost, touch)

