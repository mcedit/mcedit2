"""
    transform_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import pytest
from mceditlib.transform import RotationTransform

log = logging.getLogger(__name__)

# @pytest.skip
# def test_null_transform(pc_world, schematic_world):
#     dim = pc_world.getDimension()
#
#     sch_dim = schematic_world.getDimension()
#
#     sch_dim_transformed = RotationTransform(sch_dim,
#                                             (0, 0, 0),
#                                             0., 0., 0.)
#
#     dim.importSchematic(sch_dim_transformed, (0, 0, 0))

def test_transform(pc_world, schematic_world):
    #dim = pc_world.getDimension()

    sch_dim = schematic_world.getDimension()

    sch_dim_transformed = RotationTransform(sch_dim,
                                            sch_dim.bounds.center,
                                            0., 0., 45.)

    assert sch_dim_transformed.chunkCount() <= 2 * sch_dim.chunkCount()
    try:
        from mcedit2.worldview.schematic_worldview import displaySchematic
    except ImportError:
        log.warn("mcedit2 not available, not displaying result")
    else:
        displaySchematic(sch_dim_transformed)