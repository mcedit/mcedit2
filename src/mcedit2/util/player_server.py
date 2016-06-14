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

        _netManager.finished.connect(self._finished)

    def _writeCache(self):
        with open(_playerDataCachePath, 'wb') as f:
            nameCache = [(k.hex, v) for k, v in self.nameCache.iteritems()]
            json.dump(nameCache, f)

    def _queryServer(self, uuid, callback):
        if not isinstance(uuid, UUID):
            raise TypeError("Expected UUID, got %s", type(uuid))

        self.callbacks[uuid] = callback
        url = "https://sessionserver.mojang.com/session/minecraft/profile/{}".format(uuid.hex)
        request = QtNetwork.QNetworkRequest(url)
        reply = _netManager.get(request)
        reply.uuid = uuid

    def _finished(self, reply):
        if hasattr(reply, 'uuid'):
            self._queryFinished(reply)
        else:
            self._textureFetchFinished(reply)

    def _queryFinished(self, reply):
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

                self.nameCache[uuid] = name

                for p in props:
                    if p['name'] == 'textures':
                        textureInfo = p['value'].decode('base64')  # xxx py3
                        try:
                            textureInfo = json.loads(textureInfo)
                        except:
                            log.exception("Cannot parse texture info.")
                            continue
                        from pprint import pprint; pprint(textureInfo)
                        # timestamp = textureInfo['timestamp']
                        # profileId = textureInfo['profileId']
                        # profileName = textureInfo['profileName']
                        textures = textureInfo.get('textures')
                        if textures:
                            skin = textures.get('SKIN')
                            if skin:
                                skinURL = skin.get('url')
                                if skinURL:
                                    # get skin
                                    texturePath = os.path.join(_playerSkinsFolder, uuid.hex + '.png')

                                    request = QtNetwork.QNetworkRequest(skinURL)

                                    reply = _netManager.get(request)

                                    reply.texturePath = texturePath
                                    reply.id = id
                                    reply.name = name
                                    reply.callback = callback

                        # cape = textures.get['CAPE']
                        # if cape:
                        #     capeURL = skin.get['cape']
                        #     if capeURL:
                        #         pass


    def _textureFetchFinished(self, reply):
        texturePath = reply.texturePath
        textureImage = reply.readAll()

        with file(texturePath, 'wb') as f:
            f.write(textureImage)

        result = {
            'id': reply.id,
            'name': reply.name,
            'texturePath': texturePath,
        }
        self._writeCache()
        reply.callback(result, None)

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
            self._queryServer(uuid, callback)
        else:
            texturePath = os.path.join(_playerSkinsFolder, uuid.hex + '.png')
            if not os.path.exists(texturePath):
                self._queryServer(uuid, callback)
            else:
                log.debug("Found name and texturePath in cache")
                name = self.nameCache[uuid]
                result = {
                    'id': uuid,
                    'name': name,
                    'texturePath': texturePath,
                }
                callback(result, None)

PlayerDataCache.instance = PlayerDataCache()