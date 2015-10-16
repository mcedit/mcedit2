"""
    time_raycast
"""
from __future__ import absolute_import, division, print_function
import logging
import timeit
from mcedit2.util.raycast import rayCast
from mceditlib.geometry import Ray
from mceditlib.worldeditor import WorldEditor

log = logging.getLogger(__name__)

def main():
    filename =  "C:\Users\Rio\AppData\Roaming\.minecraft\saves\New World1_8"
    ray = Ray((1827.21, 184.79, 286.4), (.25, -.948, .18))
    editor = WorldEditor(filename, readonly=True)
    dim = editor.getDimension()
    bounds = dim.bounds
    def timeCast():
        for i in range(100):
            pos = rayCast(ray, dim)
    print("timeCast x100 in %0.2fms" % (timeit.timeit(timeCast, number=1) * 1000))
if __name__ == "__main__":
    main()
