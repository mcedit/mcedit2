"""
    conftest
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import zipfile

import pytest

from mceditlib.test.templevel import TempLevel

log = logging.getLogger(__name__)

@pytest.fixture
def pc_world():
    return TempLevel("AnvilWorld")

@pytest.fixture(params=["Station.schematic"])
def schematic_world(request):
    return TempLevel(request.param)


@pytest.fixture(params=["AnvilWorld", "Floating.schematic"])
# , "MCRWorld", "city_256_256_128.dat", "PocketWorldAdapter.zip"
def any_world(request):
    if request.param == "PocketWorldAdapter.zip":
        def unpackPocket(tmpname):
            zf = zipfile.ZipFile("test_files/PocketWorldAdapter.zip")
            zf.extractall(tmpname)
            return WorldEditor(tmpname + "/PocketWorldAdapter")

        return TempLevel("XXX", createFunc=unpackPocket)

    return TempLevel(request.param)