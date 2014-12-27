"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
log = logging.getLogger(__name__)

def lazyprop(fn):
    """
    Lazily computed property wrapper.


    >>> class Foo(object):
    ...     @lazyprop
    ...     def func(self):
    ...         print("Big computation here!")
    ...         return 42
    >>> f = Foo()
    >>> f.func
    Big computation here!
    42
    >>> f.func
    42
    >>> del f.func
    >>> f.func
    Big computation here!
    42

    :type fn: __builtin__.function
    :return:
    :rtype:
    """
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    @_lazyprop.deleter
    def _lazyprop(self):
        if hasattr(self, attr_name):
            delattr(self, attr_name)


    return _lazyprop
