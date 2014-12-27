from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtCore


def QObject_tr_unicode_literals_fix():
    """
    Because of a bug in PySide, QObject.tr will return an empty string if a unicode object is passed. Additionally,
    if a utf-8 encoded byte string is passed to tr (maybe this is only when no translations are loaded) then the
    returned string will be an incorrectly decoded unicode object (each character's code point is a single byte of the
    utf-8 encoded byte string that was passed. Thus, encode using 'ascii' and avoid using non-ascii characters
    in string literals.
    """
    _tr = QtCore.QObject.tr

    def tr(ctx, string, *a, **kw):
        if isinstance(string, unicode):
            string = string.encode('ascii')
        return _tr(ctx, string, *a, **kw)

    QtCore.QObject.tr = tr
