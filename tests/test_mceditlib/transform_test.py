"""
    transform_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import pytest
from mceditlib.selection import BoundingBox
from mceditlib.transform import DimensionTransform, SelectionTransform

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

def test_selection_transform(schematic_world):
    pytest.skip()

    selection = BoundingBox((10, 10, 10), (100, 100, 100))
    sch_dim = schematic_world.getDimension()
    sch_dim_transformed = SelectionTransform(sch_dim, selection)
    try:
        from mcedit2.worldview.schematic_worldview import displaySchematic
    except ImportError:
        log.warn("mcedit2 not available, not displaying result")
    else:
        displaySchematic(sch_dim_transformed)

def test_rotation_transform(pc_world, schematic_world):
    pytest.skip()

    sch_dim = schematic_world.getDimension()

    sch_dim_transformed = DimensionTransform(sch_dim,
                                            sch_dim.bounds.center,
                                            0., 0., 45.)

    assert sch_dim_transformed.chunkCount() <= 2 * sch_dim.chunkCount()
    try:
        from mcedit2.worldview.schematic_worldview import displaySchematic
    except ImportError:
        log.warn("mcedit2 not available, not displaying result")
    else:
        displaySchematic(sch_dim_transformed)

def test_selection_rotation_transform(schematic_world):
    pytest.skip()
    selection = BoundingBox((10, 10, 10), (100, 100, 100))
    sch_dim = schematic_world.getDimension()
    sch_dim_selection = SelectionTransform(sch_dim, selection)

    sch_dim_transformed = DimensionTransform(sch_dim_selection,
                                            sch_dim_selection.bounds.center,
                                            0., 0., 45.)

    try:
        from mcedit2.worldview.schematic_worldview import displaySchematic
    except ImportError:
        log.warn("mcedit2 not available, not displaying result")
    else:
        displaySchematic(sch_dim_transformed)
