"""
    player_server_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import uuid

import pytest as pytest
from PySide import QtCore

from mcedit2.util.player_server import PlayerDataCache

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

@pytest.fixture(params=[
    '23fc8bb1-0e5d-47d1-b43f-f19299a28ac9',
    '98b70142-3a7e-4048-90af-286ac78d7447',
    'f3dc4a5e-2fbf-4a3a-b05a-06f0bd06d2b7'])
def player_uuid(request):
    return uuid.UUID(request.param)


app = None


def test_get_name(player_uuid):
    global app
    if app is None:
        app = QtCore.QCoreApplication([])
    #loop = QtCore.QEventLoop()
    obj = {}

    def callback(result, error):
        obj['result'] = result
        assert result
        app.exit()

    PlayerDataCache.getPlayerInfo(player_uuid, callback)

    app.exec_()


