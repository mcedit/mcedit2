from benchmarks import bench_temp_level
from mceditlib.export import extractSchematicFrom

level = bench_temp_level("AnvilWorld")
schem = None

def timeExport():
    global schem
    schem = extractSchematicFrom(level, level.bounds)

def timeImport():
    level.getDimension().copyBlocks(schem, schem.bounds, (0, 0, 0))
#
#import zlib
#import regionfile
#
#compresslevel = 1
#def _deflate(data):
#    return zlib.compress(data, compresslevel)
#
#regionfile.deflate = _deflate

if __name__ == "__main__":
    import timeit
    #timeExport()
    #timeImport()
    print "Exported in %.02f" % (timeit.timeit(timeExport, number=1))
    print "Imported in %.02f" % (timeit.timeit(timeImport, number=1))
