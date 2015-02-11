"""
    minecraftinstall
"""
from __future__ import absolute_import, division, print_function
import hashlib
import re
from PySide import QtGui
import logging
import os
from PySide.QtCore import Qt
from mcedit2.resourceloader import ResourceLoader

from mcedit2.util import settings
from mcedit2.util.load_ui import load_ui
from mceditlib import directories

log = logging.getLogger(__name__)

installationsOption = settings.Settings().getOption("minecraft_installs/installations")
currentInstallOption = settings.Settings().getOption("minecraft_installs/current_install", int)

class MCInstall(object):
    def __init__(self, path, name="Unnamed"):
        self.name = name
        self.path = path

    def checkUsable(self):
        """
        Raises MCInstallError explaining why this install is unusable, or else does nothing
        :return:
        :rtype:
        """
        log.info("Checking install at %s", self.path)
        if not os.path.exists(self.path):
            raise MCInstallError("Minecraft folder does not exist.")
        if not os.path.exists(self.versionsDir):
            raise MCInstallError("Minecraft versions folder does not exist.")
        if not len(self.versions):
            raise MCInstallError("Minecraft folder has no minecraft versions")
        log.info("Found versions:\n%s", self.versions)
        requiredVersions = [v for v in self.versions if v.startswith("1.8")]
        if not len(requiredVersions):
            raise MCInstallError("Minecraft version 1.8 and up is required. Use the Minecraft Launcher to download it.")

    @property
    def versionsDir(self):
        return os.path.join(self.path, "versions")

    @property
    def versions(self):
        versions = os.listdir(self.versionsDir)
        return [v for v in versions
                if os.path.exists(self.getVersionJarPath(v))
                and usableVersion(v)]

    def getVersionJarPath(self, version):
        return os.path.join(self.versionsDir, version, "%s.jar" % version)

    @property
    def resourcePacks(self):
        return os.listdir(os.path.join(self.path, "resourcepacks"))

    def getSaveFileDir(self):
        return os.path.join(self.path, "saves")

    def getResourcePackPath(self, filename):
        return os.path.join(self.path, "resourcepacks", filename)

    def getJsonSettingValue(self):
        return {"name": self.name,
                "path": self.path}

    def getResourceLoader(self, version, resourcePack):
        loader = ResourceLoader()
        if resourcePack:
            loader.addZipFile(self.getResourcePackPath(resourcePack))
        loader.addZipFile(self.getVersionJarPath(version))
        major, minor, rev = splitVersion(version)

        # Need v1.8 for block models
        if (major, minor) < (1, 8):
            v1_8 = self.findVersion1_8()
            loader.addZipFile(self.getVersionJarPath(v1_8))

        def md5hash(filename):
            md5 = hashlib.md5()
            with file(filename, "rb") as f:
                md5.update(f.read())
                return md5.hexdigest()
        info = ["%s (%s)" % (z.filename, md5hash(z.filename)) for z in loader.zipFiles]
        log.info("Created ResourceLoader with search path:\n%s", ",\n".join(info))
        return loader

    def findVersion1_8(self):
        for v in self.versions:
            major, minor, rev = splitVersion(v)
            if (major, minor) >= (1, 8):
                if rev == "":
                    return v
                try:
                    rev = int(rev[1:])  # skip revs like ".2-pre1" and ".1-OptiFine_HD_U_C7", only accept full releases
                    return v
                except ValueError:
                    pass

def splitVersion(version):
    """
    Split a Minecraft version ID into major, minor, and revision. If the version could not be parsed, return (0, 0, "")
    The revision is returned with the leading period. For example, if "1.8.1-pre3" is passed, (1, 8, ".1-pre3") will
    be returned.

    :param version:
    :type version: unicode
    :return: major, minor, revision
    :rtype: int, int, unicode
    """
    try:
        match = re.search(r"(\d+)\.(\d+)(.*)", version)
        if match is None:
            return 0, 0, ""
        groups = match.groups()
        if len(groups) < 2:
            return 0, 0, ""
        if len(groups) < 3:
            return int(groups[0]), int(groups[1]), ""
        return int(groups[0]), int(groups[1]), groups[2]
    except ValueError:
        return 0, 0, ""

def usableVersion(version):
    """
    Return True if the version has unstitched texture data in assets/minecraft/textures/blocks (v1.6+)
    (earlier versions have unstitched textures elsewhere, so don't bother with them)
    :param version:
    :type version:
    :return:
    :rtype:
    """
    major, minor, rev = splitVersion(version)
    if major < 1:
        return False
    if minor < 6:
        return False
    return True

class MCInstallError(ValueError):
    """
    Raised for invalid or unusable Minecraft installs.
    """

def getDefaultInstall():
    """

    :return:
    :rtype: MCInstall
    """
    minecraftDir = directories.minecraftDir
    defaultInstall = MCInstall(minecraftDir, "(Default)")
    try:
        defaultInstall.checkUsable()
    except MCInstallError as e:
        log.warn("Default install not usable: %s", e)
        return None
    else:
        value = defaultInstall.getJsonSettingValue()
        if value not in installationsOption.jsonValue([]):
            _installations.append(defaultInstall)
            _saveInstalls()
        return defaultInstall

_installations = None

def _saveInstalls():
    installationsOption.setJsonValue([i.getJsonSettingValue() for i in _installations])
    log.warn("MCInstall settings: %s", installationsOption.jsonValue())

def _listInstalls():
    for install in installationsOption.jsonValue([]):
        name = install["name"]
        path = install["path"]
        try:
            install = MCInstall(path, name)
            install.checkUsable()
            yield install
        except MCInstallError as e:
            log.warn("Not using install %s: %s", install.path, e)


def listInstalls():
    global _installations
    if _installations is None:
        _installations = list(_listInstalls())
    getDefaultInstall()

    return _installations

def selectedInstallIndex():
    return currentInstallOption.value(0)

def getInstall(index):
    return _installations[index]

def ensureInstallation():
    """
    Called on app startup. Auto-detect install, display config dialog if no installs were found
    :return:
    :rtype:
    """
    listInstalls()

    #raise MCInstallError("Displaying Minecraft Install dialog! xxx remove me")
    if not len(_installations):
        msgBox = QtGui.QMessageBox()
        msgBox.setText("No usable Minecraft installs were found. MCEdit requires an installed Minecraft version to "
                       "access block textures, models, and metadata. Minecraft 1.8 or greater is required.")
        #msgBox.setInformativeText(e.message)
        msgBox.exec_()
        installsWidget = MinecraftInstallsDialog()
        installsWidget.exec_()

class NameItem(QtGui.QTableWidgetItem):
    def setData(self, data, role):
        if role != Qt.EditRole or data != "(Default)":
            super(NameItem, self).setData(data, role)

class PathItem(QtGui.QTableWidgetItem):
    def setData(self, data, role):
        if role != Qt.EditRole or os.path.exists(data):
            super(PathItem, self).setData(data, role)


class MinecraftInstallsDialog(QtGui.QDialog):
    def __init__(self, *args, **kwargs):
        super(MinecraftInstallsDialog, self).__init__(*args, **kwargs)
        load_ui("minecraft_installs.ui", baseinstance=self)
        # populate list view
        for row, install in enumerate(listInstalls()):
            self._addInstall(install)

        self._hiliteRow(currentInstallOption.value(0))

        self.tableWidget.cellChanged.connect(self.itemChanged)
        #self.tableWidget.doubleClicked.connect(self.select)
        self.addButton.clicked.connect(self.add)
        self.removeButton.clicked.connect(self.remove)
        self.selectButton.clicked.connect(self.select)
        #self.editButton.clicked.connect(self.edit)
        self.okButton.clicked.connect(self.ok)

    def itemChanged(self, row, column):
        install = _installations[row]
        text = self.tableWidget.item(row, column).text()
        if column == 0:
            install.name = text
        if column == 2:
            install.path = text


    def _addInstall(self, install):
        tableWidget = self.tableWidget
        row = tableWidget.rowCount()
        tableWidget.setRowCount(row+1)
        nameItem = NameItem(install.name)
        if install.name == "(Default)":
            nameItem.setFlags(nameItem.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row, 0, nameItem)

        versionsString = ", ".join(sorted(install.versions, reverse=True))
        versionsItem = QtGui.QTableWidgetItem(versionsString)
        versionsItem.setFlags(versionsItem.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row, 1, versionsItem)

        pathItem = PathItem(install.path)
        if install.name == "(Default)":
            pathItem.setFlags(pathItem.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row, 2, pathItem)
        self._hiliteRow(row)
        currentInstallOption.setValue(row)
        _saveInstalls()

    def _hiliteRow(self, hiliteRow):
        for row in range(self.tableWidget.rowCount()):
            for column in range(self.tableWidget.columnCount()):
                item = self.tableWidget.item(row, column)
                font = item.font()
                font.setBold(row == hiliteRow)
                item.setFont(font)

    def add(self):
        folder = QtGui.QFileDialog.getExistingDirectory(self, "Choose a Minecraft installation folder (.minecraft)")
        if not folder:
            return
        try:
            install = MCInstall(folder)
            install.checkUsable()
        except MCInstallError as e:
            message = "This minecraft install is unusable.\n(%s)" % e.message
            QtGui.QMessageBox.warning(self, "Minecraft Install Unusable", message)
        else:
            _installations.append(install)
            self._addInstall(install)

    def remove(self):
        row = self.tableWidget.currentRow()
        del _installations[row]
        self.tableWidget.removeRow(row)
        _saveInstalls()

    def select(self):
        row = self.tableWidget.currentRow()
        currentInstallOption.setValue(row)
        self._hiliteRow(row)

    def ok(self):
        self.close()

    def close(self):
        if not len(_installations):
            button = QtGui.QMessageBox.critical(self,
                                                "Minecraft Install Needed",
                                                "Cannot start MCEdit without at least one Minecraft installation version "
                                                "1.8 or greater.",
                                                QtGui.QMessageBox.Close | QtGui.QMessageBox.Cancel,
                                                QtGui.QMessageBox.Cancel)

            if button == QtGui.QMessageBox.Close:
                raise SystemExit
        else:
            super(MinecraftInstallsDialog, self).close()
