"""
    conftest
"""

from os.path import dirname

import py
import pytest

from mceditlib.worldeditor import WorldEditor


_TEST_FILES_DIR = "test_files"

# from $PROJECT/src/mceditlib/test/templevel.py, get to $PROJECT/test_files

_PROJECT = dirname(dirname(dirname(dirname(__file__))))
TEST_FILES_DIR = py.path.local(_PROJECT).join(_TEST_FILES_DIR)

@pytest.fixture
def temp_level(temp_file):
    return WorldEditor(temp_file.strpath)

@pytest.fixture
def temp_file(tmpdir, request):
    filename = request.param
    source = TEST_FILES_DIR.join(filename)
    assert source.exists()

    target = tmpdir.join(filename)
    source.copy(target)

    return target

@pytest.fixture
def indev_file(tmpdir):
    return TempFile(tmpdir, "indev.mclevel")


@pytest.fixture
def pc_world(tmpdir):
    return TempLevel(tmpdir, "AnvilWorld")


@pytest.fixture(params=["Station.schematic"])
def schematic_world(tmpdir, request):
    return TempLevel(tmpdir, request.param)


@pytest.fixture(params=["AnvilWorld", "Floating.schematic"])
def any_world(request):
    if request.param == "PocketWorldAdapter.zip":
        raise NotImplementedError("Pocket worlds not implemented")
        # def unpackPocket(tmpname):
        #     zf = zipfile.ZipFile("test_files/PocketWorldAdapter.zip")
        #     zf.extractall(tmpname)
        #     return WorldEditor(tmpname + "/PocketWorldAdapter")

        # return TempLevel("XXX", createFunc=unpackPocket)

    return TempLevel(request.param)