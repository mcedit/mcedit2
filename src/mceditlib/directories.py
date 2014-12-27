"""
   directories.py

   On initialization, finds the default location for Minecraft saves
   and stores it in saveFileDir.
"""

from __future__ import absolute_import

import sys
import os
from mceditlib import util

if sys.platform == "win32":
    appDataDir = util.win32_appdata()
    minecraftDir = os.path.join(appDataDir, u".minecraft")
    appSupportDir = os.path.join(appDataDir, u"mceditlib")

elif sys.platform == "darwin":
    appDataDir = os.path.expanduser(u"~/Library/Application Support")
    minecraftDir = os.path.join(appDataDir, u"minecraft")
    appSupportDir = os.path.expanduser(u"~/Library/Application Support/mceditlib/")

else:
    appDataDir = os.path.expanduser(u"~")
    minecraftDir = os.path.expanduser(u"~/.minecraft")
    appSupportDir = os.path.expanduser(u"~/.mceditlib")

saveFileDir = os.path.join(minecraftDir, u"saves")

