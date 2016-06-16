"""
    conftest
"""

from os.path import dirname, basename

import py
import pytest

import logging
logging.basicConfig(level=logging.INFO)

from mceditlib.worldeditor import WorldEditor


_TEST_FILES_DIR = "test_files"

# from $PROJECT/tests/conftest.py, get to $PROJECT/test_files

_PROJECT = dirname(dirname(__file__))
TEST_FILES_DIR = py.path.local(_PROJECT).join(_TEST_FILES_DIR)

@pytest.fixture
def temp_file(tmpdir, request):
    return copy_temp_file(tmpdir, request.param)

def copy_temp_level(tmpdir, filename):
    return WorldEditor(copy_temp_file(tmpdir, filename).strpath)

def copy_temp_file(tmpdir, filename):
    source = TEST_FILES_DIR.join(filename)
    assert source.exists()

    target = tmpdir.join(basename(filename))
    source.copy(target)

    return target

@pytest.fixture
def indev_file(tmpdir):
    return copy_temp_file(tmpdir, "indev.mclevel")


@pytest.fixture
def pc_world(tmpdir):
    return copy_temp_level(tmpdir, "AnvilWorld")

@pytest.fixture
def testbed_schem(tmpdir):
    return copy_temp_level(tmpdir, "testbed.schematic")


@pytest.fixture(params=["Station.schematic"])
def schematic_world(tmpdir, request):
    return copy_temp_level(tmpdir, request.param)


@pytest.fixture(params=["AnvilWorld", "Floating.schematic"])
def any_world(tmpdir, request):
    if request.param == "PocketWorldAdapter.zip":
        raise NotImplementedError("Pocket worlds not implemented")
        # def unpackPocket(tmpname):
        #     zf = zipfile.ZipFile("test_files/PocketWorldAdapter.zip")
        #     zf.extractall(tmpname)
        #     return WorldEditor(tmpname + "/PocketWorldAdapter")

        # return TempLevel("XXX", createFunc=unpackPocket)

    return copy_temp_level(tmpdir, request.param)