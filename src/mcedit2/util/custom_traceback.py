"""
    custom_traceback
"""
from __future__ import absolute_import, division, print_function
import logging
import sys
from collections import namedtuple

log = logging.getLogger(__name__)


import traceback

_MCETraceFrame = namedtuple('_MCETraceFrame', 'filename lineno name line')


class MCETraceFrame(_MCETraceFrame):
    def __new__(cls, *args):
        return _MCETraceFrame.__new__(cls, *args[:-1])

    def __init__(self, *args):
        _MCETraceFrame.__init__(self, *args[:-1])
        self.selfstr = args[-1]


def extract_tb(tb, limit=None):
    """Return list of up to limit pre-processed entries from traceback.

    This is useful for alternate formatting of stack traces.  If
    'limit' is omitted or None, all entries are extracted.  A
    pre-processed stack trace entry is a 5-tuple (filename, line
    number, function name, text, selfstr) representing the information that is
    usually printed for a stack trace.  The text is a string with
    leading and trailing whitespace stripped; if the source is not
    available it is None.

    This function is modified to return the name of the 'self' parameter's class as
    the 5th element of the tuple.
    """
    if limit is None:
        if hasattr(sys, 'tracebacklimit'):
            limit = sys.tracebacklimit
    list = []
    n = 0
    while tb is not None and (limit is None or n < limit):
        f = tb.tb_frame
        lineno = tb.tb_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        self = f.f_locals.get('self')
        try:
            selfstr = self and "(self is a {0})".format(self.__class__.__name__) or " "
            if hasattr(self, 'name'):
                selfstr += "(named %s)" % self.name
        except:
            selfstr = " "
        traceback.linecache.checkcache(filename)
        line = traceback.linecache.getline(filename, lineno, f.f_globals)
        if line:
            line = line.strip()
        else:
            line = None
        list.append(MCETraceFrame(filename, lineno, name, line, selfstr))
        tb = tb.tb_next
        n = n + 1
    return list


def format_list(extracted_list):
    """Format a list of traceback entry tuples for printing.

    Given a list of tuples as returned by extract_tb() or
    extract_stack(), return a list of strings ready for printing.
    Each string in the resulting list corresponds to the item with the
    same index in the argument list.  Each string ends in a newline;
    the strings may contain internal newlines as well, for those items
    whose source text line is not None.

    This function is modified to include the 5th item of the tuple as
    the name of the class of the 'self' parameter.
    """
    list = []
    for frame in extracted_list:
        filename, lineno, name, line = frame
        selfstr = getattr(frame, 'selfstr', None)

        item = '  File "%s", line %d, in %s %s\n' % (filename, lineno, name, selfstr[:60])
        if line:
            item = item + '    %s\n' % line.strip()
        list.append(item)
    return list


def print_list(extracted_list, file=None):
    """Print the list of tuples as returned by extract_tb() or
    extract_stack() as a formatted stack trace to the given file.

    This function is modified to print the 5th element of the tuple
     returned by the modified functions above.
    """
    if file is None:
        file = sys.stderr
    for entry in extracted_list:
        filename, lineno, name, line = entry
        selfstr = getattr(entry, 'selfstr', None)

        print('  File "%s", line %d, in %s %s' % (filename, lineno, name, selfstr),
              file=file)
        if line:
            print('    %s' % line.strip(), file=file)


def print_tb(tb, limit=None, file=None):
    """Print up to 'limit' stack trace entries from the traceback 'tb'.

    If 'limit' is omitted or None, all entries are printed.  If 'file'
    is omitted or None, the output goes to sys.stderr; otherwise
    'file' should be an open file or file-like object with a write()
    method.

    This function is modified to also print the name of the 'self' parameter's class.
    """
    if file is None:
        file = sys.stderr
    if limit is None:
        if hasattr(sys, 'tracebacklimit'):
            limit = sys.tracebacklimit
    n = 0
    _print = traceback._print
    while tb is not None and (limit is None or n < limit):
        f = tb.tb_frame
        lineno = tb.tb_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        self = f.f_locals.get('self')
        try:
            selfstr = self and "(self is a {0})".format(self.__class__.__name__) or " "
        except:
            selfstr = " "
        _print(file,
               '  File "%s", line %d, in %s %s' % (filename, lineno, name, selfstr))
        linecache = traceback.linecache
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        if line: _print(file, '    ' + line.strip())
        tb = tb.tb_next
        n += 1


def install():
    traceback.extract_tb = extract_tb
    traceback.format_list = format_list
    traceback.print_list = print_list
    traceback.print_tb = print_tb
