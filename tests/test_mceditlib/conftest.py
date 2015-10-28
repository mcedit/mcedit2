"""
    conftest
"""

from os.path import dirname, basename

import py
import pytest

from mceditlib.worldeditor import WorldEditor


_TEST_FILES_DIR = "test_files"

# from $PROJECT/tests/test_mceditlib/conftest.py, get to $PROJECT/test_files

_PROJECT = dirname(dirname(dirname(__file__)))
TEST_FILES_DIR = py.path.local(_PROJECT).join(_TEST_FILES_DIR)

@pytest.fixture
def temp_file(tmpdir, request):
    return _temp_file(tmpdir, request.param)

def _temp_level(tmpdir, filename):
    return WorldEditor(_temp_file(tmpdir, filename).strpath)

def _temp_file(tmpdir, filename):
    source = TEST_FILES_DIR.join(filename)
    assert source.exists()

    target = tmpdir.join(basename(filename))
    source.copy(target)

    return target

@pytest.fixture
def indev_file(tmpdir):
    return _temp_file(tmpdir, "indev.mclevel")


@pytest.fixture
def pc_world(tmpdir):
    return _temp_level(tmpdir, "AnvilWorld")


@pytest.fixture(params=["Station.schematic"])
def schematic_world(tmpdir, request):
    return _temp_level(tmpdir, request.param)


@pytest.fixture(params=["AnvilWorld", "Floating.schematic"])
def any_world(tmpdir, request):
    if request.param == "PocketWorldAdapter.zip":
        raise NotImplementedError("Pocket worlds not implemented")
        # def unpackPocket(tmpname):
        #     zf = zipfile.ZipFile("test_files/PocketWorldAdapter.zip")
        #     zf.extractall(tmpname)
        #     return WorldEditor(tmpname + "/PocketWorldAdapter")

        # return TempLevel("XXX", createFunc=unpackPocket)

    return _temp_level(tmpdir, request.param)