"""
    unique_nd
"""
from __future__ import absolute_import, division, print_function
import logging

log = logging.getLogger(__name__)


import numpy as np

def unique_nd(ar, return_index=False, return_inverse=False):
    """
    Find the unique n-dimensional sections (columns, planes, cubes, etc)
    of an array. Sections are ordered along the last axis.

    Returns the sorted unique sections of an array. The last row of the column is used
    as the first sort key (see `np.lexsort` for details.) There are two optional
    outputs in addition to the unique elements: the indices of the input array
    (along the last axis) that give the unique values, and the indices of the unique
    array (also along the last axis) that reconstruct the input array.

    Modified to sort n-dimensional elements spanning all but the last axis, ordered
    along the last axis. See `np.lexsort`. Note that since `np.lexsort` is not stable,
    the indexes returned by return_index will not reconstruct the original array if
    and only if the array values are a type with an unstable sort order (i.e. two items
    that are otherwise inequal can be sorted either before or after one another.)
    This is not the case for int and float values.

    Parameters
    ----------
    ar : array_like
        Input array.
    return_index : bool, optional
        If True, also return the indices along the last axis of `ar` that result in the unique
        array.
    return_inverse : bool, optional
        If True, also return the indices along the last axis of the unique array that can be used
        to reconstruct `ar`.

    Returns
    -------
    unique : ndarray
        The sorted unique values.
    unique_indices : ndarray, optional
        The indices of the first occurrences of the unique columns in the
        original array. Only provided if `return_index` is True.
    unique_inverse : ndarray, optional
        The indices to reconstruct the original array from the
        unique array. Only provided if `return_inverse` is True.

    See Also
    --------
    numpy.lib.arraysetops : Module with a number of other functions for
                            performing set operations on arrays.

    Examples
    --------
    >>> unique_nd([1, 1, 2, 2, 3, 3])
    array([1, 2, 3])
    >>> a = np.array([[1, 5, 4], [3, 2, 2]])
    >>> unique_nd(a)
    array([2, 3, 1])

    Return the indices of the original array that give the unique values:

    >>> a = np.array([['a', 'c', 'b', 'c'],
    ...               ['c', 'a', 'b', 'a']])
    >>> u, indices = unique_nd(a, return_index=True)
    >>> u
    array([['c', 'b', 'a'],
           ['a', 'b', 'c']],
           dtype='|S1')
    >>> indices
    array([1, 2, 0])
    >>> a[..., indices]
    array([['c', 'b', 'a'],
           ['a', 'b', 'c']],
           dtype='|S1')

    Reconstruct the input array from the unique values:

    >>> a = np.array([[1, 2, 6, 4],
    ...               [2, 3, 2, 1]])
    >>> u, indices = unique_nd(a, return_inverse=True)
    >>> u
    array([[4, 1, 6, 2],
           [1, 2, 2, 3]])
    >>> indices
    array([1, 3, 2, 0])
    >>> u[..., indices]
    array([[1, 2, 6, 4],
           [2, 3, 2, 1]])

    """

    if ar.size == 0:
        if return_inverse and return_index:
            return ar, np.empty(0, np.bool), np.empty(0, np.bool)
        elif return_inverse or return_index:
            return ar, np.empty(0, np.bool)
        else:
            return ar

    if return_inverse or return_index:
        perm = np.lexsort(ar)
        aux = ar[..., perm]
        flag = np.concatenate(([True], (aux[..., 1:] != aux[..., :-1])[-1]), axis=-1)
        if return_inverse:
            iflag = np.cumsum(flag) - 1
            iperm = perm.argsort()
            if return_index:
                return aux[..., flag], perm[..., flag], iflag[..., iperm]
            else:
                return aux[..., flag], iflag[..., iperm]
        else:
            return aux[..., flag], perm[..., flag]

    else:
        ar = ar[..., np.lexsort(ar)]
        flag = np.concatenate(([True], (ar[..., 1:] != ar[..., :-1])[-1]), axis=-1)
        return ar[..., flag]

