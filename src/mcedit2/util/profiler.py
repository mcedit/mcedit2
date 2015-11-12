"""
    profiler
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import deque, defaultdict
import contextlib
import logging
import time
import datetime
import functools

import sys

from mceditlib.util.lazyprop import lazyprop


log = logging.getLogger(__name__)

ENABLE_PROFILER = True

if sys.platform == "win32":
    clock = time.clock
else:
    clock = time.time

class Profiler(object):
    sampleLimit = 100000
    sampleTimeLimit = 10.000
    def __init__(self):
        self.nameStack = deque(["root"])

        self.samples = deque(maxlen=self.sampleLimit)
        self.recordSample(True)
        #atexit.register(self.dumpSamples)

    def dumpSamples(self):
        with file("samples.txt", "w") as f:
            for name, time, entry in self.samples:
                f.write("%s: %s (%s)\n" % (datetime.datetime.fromtimestamp(time), name, entry))

    def enter(self, name, entry=True):
        """
        Record the entry into a named profiling area. Call profiler.exit() to return to the previous area.

        :param name:
        :type name:
        :return:
        :rtype:
        """
        #log.debug("enter %s", name)
        self.nameStack.append(name)
        self.recordSample(entry)

    def exit(self):
        #log.debug("exit %s", self.nameStack[-1])
        self.nameStack.pop()
        self.recordSample()

    @contextlib.contextmanager
    def context(self, name, entry=True):
        self.enter(name, entry)
        try:
            yield
        finally:
            self.exit()

    def function(self, name):
        def _decorate(func):
            log.debug("Decorating %s with %s", func, name)
            @functools.wraps(func)
            def _wrapper(*a, **kw):
                with self.context(name):
                    return func(*a, **kw)
            return _wrapper

        if hasattr(name, '__call__'):
            func = name
            name = func.__name__
            return _decorate(func)

        return _decorate

    def iterate(self, it, name):
        first = True
        while True:
            with self.context(name, first):
                val = it.next()

            first = False
            yield val


    def iterator(self, name):
        def _decorate(func):
            log.debug("Decorating %s with %s", func, name)
            @functools.wraps(func)
            def _wrapper(*a, **kw):
                return self.iterate(func(*a, **kw), name)
            return _wrapper

        if hasattr(name, '__call__'):
            func = name
            name = func.__name__
            return _decorate(func)

        return _decorate

    def recordSample(self, entry=False):
        self.samples.append(('/'.join(self.nameStack), clock(), entry))
        if self.sampleTimeLimit is not None:
            while len(self.samples) and self.samples[-1][1] - self.samples[0][1] > self.sampleTimeLimit:
                self.samples.popleft()

    def analyze(self):
        times = defaultdict(float)
        counts = defaultdict(int)
        lastPath, lastTime, _ = self.samples[0]

        for path, time, entry in self.samples:
            times[lastPath] += time - lastTime
            if entry:
                counts[path] += 1
            lastTime = time
            lastPath = path

        return ProfileAnalysis(times.items(), counts)

class DummyProfiler(Profiler):
    def enter(self, name, entry=False):
        return

    def exit(self):
        return

    def function(self, name):
        if isinstance(name, basestring):
            def f(a):
                return a
            return f
        else:
            return name

    #def iterator(self, name=None):
    #    return lambda f:f if isinstance(name, basestring) else return name

    def iterate(self, it, name):
        return it

class AnalysisNode(defaultdict):
    def __init__(self, **kwargs):
        super(AnalysisNode, self).__init__(AnalysisNode, **kwargs)
        self.samples = []
        self.ncalls = 0

    @lazyprop
    def totalTime(self):
        time = sum(self.samples)
        for leaf in self.values():
            time += leaf.totalTime
        return time


class ProfileAnalysis(AnalysisNode):
    def __init__(self, times, counts, **kwargs):
        super(ProfileAnalysis, self).__init__(**kwargs)
        for path, seconds in times:
            leaf = self

            parts = path.split("/")
            for p in parts:
                leaf = leaf[p]
                leaf.name = p

            leaf.samples.append(seconds)
            leaf.ncalls += counts[path]

_commonProfiler = None


def getProfiler():
    global _commonProfiler
    if _commonProfiler is None:
        if ENABLE_PROFILER:
            _commonProfiler = Profiler()
        else:
            _commonProfiler = DummyProfiler()

    return _commonProfiler


def function(name):
    """
    Decorate a function with profiler calls. If name is not given, uses the function's name.

    Usage:

    @profiler.function
    def foo():
        print "Work work."

    @profiler.function("Subroutine 'bar' #2")
    def bar():
        print "Work work work."

    :param name:
    :return: :rtype: function
    """
    return getProfiler().function(name)


def context(*a, **kw):
    return getProfiler().context(*a, **kw)


def iterate(it, name):
    """
    Wraps an iterator with profiler calls. Each call to it.next() is wrapped in a Profiler.context() call.

    Usage:

    someIterator = xrange(1000)
    for i in profiler.iterate(someIterator, "Costly foo iteration."):
        print i

    :type it: __builtin__.generator
    :type name: unicode or str
    """
    return getProfiler().iterate(it, name)

def iterator(name=None):
    """
    Decorates a function which returns an iterator by wrapping the iterator with profile calls.
    If name is not given, uses the function's name.

    Usage:

    @profiler.iterator
    def foo_iter():
        for i in range(100):
            yield i

    @profiler.iterator("Iterator 'bar' #2")
    def bar_iter():
        for i in range(100):
            yield i



    :type name: unicode or str
    :return: :rtype: function
    """
    return getProfiler().iterator(name)
