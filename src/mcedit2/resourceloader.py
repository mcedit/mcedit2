"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
import zipfile
import re

log = logging.getLogger(__name__)

class ResourceNotFound(KeyError):
    pass

class ResourceLoader(object):
    def __init__(self, fallbackZipFile):
        super(ResourceLoader, self).__init__()
        self.zipFiles = []
        self.modsDirs = []
        self.fallbackZipFile = zipfile.ZipFile(fallbackZipFile)

    def addZipFile(self, zipPath):
        try:
            zf = zipfile.ZipFile(zipPath)
        except zipfile.BadZipfile as e:
            raise IOError("Could not read %s as a zip file." % zipPath)
        self.zipFiles.append(zf)

    def addModsFolder(self, modsDir):
        modsDir = os.path.normpath(modsDir)
        if modsDir in self.modsDirs:
            return
        self.modsDirs.append(modsDir)

        for modName in os.listdir(modsDir):
            mod = os.path.join(modsDir, modName)
            if not os.path.isfile(mod):
                continue
            if not zipfile.is_zipfile(mod):
                continue

            try:
                self.addZipFile(mod)
            except Exception as e:
                log.exception("Failed to add mod %s to resource loader.", modName)
                continue

    def openStream(self, path, fallback=False):
        if fallback:
            try:
                stream = self.fallbackZipFile.open(path)
            except KeyError:  # Not found in zip file
                raise ResourceNotFound("Resource %s not found in search path" % path)
            return stream

        for zipFile in self.zipFiles:
            try:
                stream = zipFile.open(path)
                break
            except KeyError:  # Not found in zip file
                continue
        else:
            raise ResourceNotFound("Resource %s not found in search path" % path)

        return stream

    def blockModelPaths(self):
        for zf in self.zipFiles:
            for name in zf.namelist():
                if name.startswith("assets/minecraft/models/block"):
                    yield name

    def blockTexturePaths(self):
        seen = set()
        for zf in self.zipFiles:
            for name in zf.namelist():
                if name in seen:
                    continue
                seen.add(name)
                if re.match(r'assets/\w+/textures/blocks/.*\.png$', name):
                    yield zf.filename, name
