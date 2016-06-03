"""
    player_server
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import logging
import os
from uuid import UUID

import sys
from PySide import QtNetwork, QtCore

from mcedit2.util import directories
from mcedit2.util.load_png import loadPNGTexture

log = logging.getLogger(__name__)


_playerDataFolder = os.path.join(directories.getUserFilesDirectory(), "player_data")
_playerSkinsFolder = os.path.join(_playerDataFolder, "skins")
_playerDataCachePath = os.path.join(_playerDataFolder, "players.json")

if not os.path.exists(_playerSkinsFolder):
    os.makedirs(_playerSkinsFolder)

_netManager = QtNetwork.QNetworkAccessManager()


class PlayerServerError(IOError):
    pass


class PlayerDataCache(QtCore.QObject):
    def __init__(self):
        super(PlayerDataCache, self).__init__()
        if os.path.exists(_playerDataCachePath):
            with open(_playerDataCachePath, 'rb') as f:
                try:
                    nameCache = json.load(f)
                    self.nameCache = {UUID(k): v for k, v in nameCache}
                except:
                    log.exception("Error while loading player data cache.")
                    self.nameCache = {}
        else:
            self.nameCache = {}

        self.callbacks = {}

        _netManager.finished.connect(self._queryFinished)

    def _writeCache(self):
        with open(_playerDataCachePath, 'wb') as f:
            nameCache = [(k.hex, v) for k, v in self.nameCache.iteritems()]
            json.dump(nameCache, f)

    def _queryServer(self, uuid, callback):
        assert isinstance(uuid, UUID)
        self.callbacks[uuid] = callback
        url = "https://sessionserver.mojang.com/session/minecraft/profile/{}".format(uuid.hex)
        request = QtNetwork.QNetworkRequest(url)
        reply = _netManager.get(request)
        reply.uuid = uuid

    def _queryFinished(self, reply):
        """

        Parameters
        ----------
        reply : QtNetwork.QNetworkReply

        Returns
        -------

        """
        uuid = reply.uuid
        data = reply.readAll()
        if uuid in self.callbacks:
            callback = self.callbacks.pop(uuid)
        else:
            callback = lambda arg, err: None
        try:
            jsonData = json.loads(str(data))
        except:
            log.exception("Error reading JSON from session server.")
            callback(None, sys.exc_value)
        else:
            if 'error' in jsonData:
                callback(None, PlayerServerError(jsonData))
            else:
                id = UUID(jsonData['id'])
                name = jsonData['name']
                props = jsonData['properties']
                textureImage = None

                for p in props:
                    if p['name'] == 'textures':
                        textureImage = p['value'].decode('base64')  # xxx py3

                self.nameCache[uuid] = name

                if textureImage is None:
                    texturePath = None
                else:
                    texturePath = os.path.join(_playerSkinsFolder, uuid.hex + '.png')

                with file(texturePath, 'wb') as f:
                    f.write(textureImage)

                result = {
                    'id': id,
                    'name': name,
                    'texturePath': texturePath,
                }
                self._writeCache()
                callback(result, None)

    # len({'id': '23fc8bb10e5d47d1b43ff19299a28ac9', 'name': 'Denox69', 'properties': [{'name': 'textures', 'value': 'eyJ0aW1lc3...WNyYWZ0Lm5ldC90ZXh0dXJlLzQxMzVkNzQxYTRjYjFmMTA1Mjc1NDU4ZDRhMWE2OWYyOGE4MjU4NjY3NWY4ZjQ0MTJjNjRiYmQyNGU5MGJjIn19fQ=='}]})

    @staticmethod
    def getPlayerInfo(uuid, callback):
        PlayerDataCache.instance._getPlayerInfo(uuid, callback)

    def _getPlayerInfo(self, uuid, callback):
        """
        Get the name and texture image for the player with the given UUID. The callback
        function will be passed the name and image path with this call signature:

            def callback(result, error):
                pass

        If an error occurs, error will be an Exception object containing the error and the
        result will be None, otherwise the result will be a dict with the keys 'id',
        'name', and 'texturePath'

        Parameters
        ----------
        uuid : UUID
        callback : Callable(tuple or None, Exception or None)

        Returns
        -------
        None
        """
        if uuid not in self.nameCache:
            self.callbacks[uuid] = callback
            self._queryServer(uuid, callback)
        else:
            texturePath = os.path.join(_playerSkinsFolder, uuid.hex + '.png')
            if not os.path.exists(texturePath):
                self._queryServer(uuid, callback)
            else:
                name = self.nameCache[uuid]
                result = {
                    'id': uuid,
                    'name': name,
                    'texturePath': texturePath,
                }
                callback(result, None)

PlayerDataCache.instance = PlayerDataCache()