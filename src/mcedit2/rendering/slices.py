"""
    slices
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy

log = logging.getLogger(__name__)

_XYZ = numpy.s_[..., 0:3]
_ST = numpy.s_[..., 3:5]
_XYZST = numpy.s_[..., :5]
_SL = numpy.s_[..., 5]
_BL = numpy.s_[..., 6]
_SLBL = numpy.s_[..., 5:7]
_RGBA = numpy.s_[..., -4:]
_RGB = numpy.s_[..., -4:-1]
_A = numpy.s_[..., -1]
