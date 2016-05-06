"""
    rotation
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mceditlib.blocktypes import parseBlockstate, joinBlockstate, PCBlockTypeSet

log = logging.getLogger(__name__)


def blankRotationTable():
    table = numpy.indices((32768, 16))

    # Roll array so table[x, y] returns [x, y]
    table = numpy.rollaxis(numpy.rollaxis(table, 1), 2, 1)
    return table


def yAxisTable(blocktypes):
    mapping = {
        'north': 'east',
        'east': 'south',
        'south': 'west',
        'west': 'north',
    }

    rail_shapes = {
        'ascending_north': 'ascending_east',
        'ascending_east': 'ascending_south',
        'ascending_south': 'ascending_west',
        'ascending_west': 'ascending_north',
        'east_west': 'north_south',
        'north_east': 'south_east',
        'south_east': 'south_west',
        'south_west': 'north_west',
        'north_west': 'north_east',

    }
    table = blankRotationTable()

    for block in blocktypes:
        stateString = block.blockState
        if not len(stateString):
            continue

        try:
            state = parseBlockstate(stateString)
        except:
            log.exception("Error parsing blockstate: %s", stateString)
            continue

        # First pass: facing=north and similar
        newState = {}
        for k, v in state.items():
            n = mapping.get(v)
            if n:
                newState[k] = n
            else:
                newState[k] = v

        state = newState
        newState = dict(state)

        # Second pass: north=true and similar
        for k, v in mapping.items():
            if k in state:
                if state[k] == 'true':
                    newState[k] = 'false'
                    newState[v] = 'true'

        # For signs and banners: rotation=10 and similar
        # y-axis only

        state = newState

        if 'rotation' in state:
            rotation = (int(state['rotation']) + 4) % 16
            state['rotation'] = unicode(rotation)

        # For logs and such: axis=x and similar

        if 'axis' in state:
            axis = state['axis']

            # y-axis only
            if axis == 'x':
                axis = 'z'
            elif axis == 'z':
                axis = 'x'

            state['axis'] = axis

        # For rails, powered rails, etc: shape=north_east
        # y-axis only

        if 'shape' in state:
            shape = state['shape']

            newShape = rail_shapes.get(shape)
            if newShape:
                state['shape'] = newShape


        #print("Changed %s \nto %s" % (stateString, newStateString))

        newBlock = blocktypes.matchingState(block.internalName, state)
        if newBlock is block:
            pass
        elif newBlock is None:
            newStateString = joinBlockstate(state)
            # print("no mapping for %s%s" % (block.internalName, newStateString))
        else:
            # print("Changed %s \nto %s" % (block, newBlock))
            table[block.ID, block.meta] = [newBlock.ID, newBlock.meta]

    return table

def xxxtest_yAxisTable():
    from . import PCBlockTypeSet
    blocktypes = PCBlockTypeSet()
    table = yAxisTable(blocktypes)

    assert (table != blankRotationTable()).any(), "Table is blank"

    changed = False
    changedNames = set()
    for i in range(32768):
        for j in range(16):
            e = table[i,j]
            if e[0] != i or e[1] != j:
                changed = True
                name = blocktypes[i, j].internalName
                if name not in changedNames:
                    # print("%s is changed" % name)
                    changedNames.add(name)

    assert changed, "Table is unchanged"

def main():
    from timeit import timeit
    blocktypes = PCBlockTypeSet()

    secs = timeit(lambda: yAxisTable(blocktypes), number=1)
    print("Time: %0.3f" % secs)

    assert secs < 0.1

if __name__ == '__main__':
    main()