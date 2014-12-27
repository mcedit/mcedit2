"""
    flowlayout

/****************************************************************************
 **
 ** Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
 ** Contact: http://www.qt-project.org/legal
 **
 ** This file is part of the examples of the Qt Toolkit.
 **
 ** $QT_BEGIN_LICENSE:BSD$
 ** You may use this file under the terms of the BSD license as follows:
 **
 ** "Redistribution and use in source and binary forms, with or without
 ** modification, are permitted provided that the following conditions are
 ** met:
 **   * Redistributions of source code must retain the above copyright
 **     notice, this list of conditions and the following disclaimer.
 **   * Redistributions in binary form must reproduce the above copyright
 **     notice, this list of conditions and the following disclaimer in
 **     the documentation and/or other materials provided with the
 **     distribution.
 **   * Neither the name of Digia Plc and its Subsidiary(-ies) nor the names
 **     of its contributors may be used to endorse or promote products derived
 **     from this software without specific prior written permission.
 **
 **
 ** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 ** "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 ** LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 ** A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 ** OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 ** SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 ** LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 ** DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 ** THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 ** (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 ** OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
 **
 ** $QT_END_LICENSE$
 **
 ****************************************************************************/

Translated to Python/PySide by David Vierra
"""
from __future__ import absolute_import, division, print_function
import logging

log = logging.getLogger(__name__)

from PySide import QtGui, QtCore


class FlowLayout(QtGui.QLayout):
    def __init__(self, parent=None, margin=-1, hSpacing=-1, vSpacing=-1):
        QtGui.QLayout.__init__(self, parent)
        self.vSpacing = vSpacing
        self.hSpacing = hSpacing
        self.margin = margin
        self.setContentsMargins(margin, margin, margin, margin)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def horizontalSpacing(self):
        if self.hSpacing >= 0:
            return self.hSpacing
        else:
            return self.smartSpacing(QtGui.QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self.vSpacing >= 0:
            return self.vSpacing
        else:
            return self.smartSpacing(QtGui.QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= self.count():
            #raise IndexError("Asked for item %d in list of length %d" % (index, self.count()))
            return None
        return self.itemList[index]

    def expandingDirections(self):
        return 0

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QtCore.QSize(2*self.margin, 2*self.margin)
        return size

    def doLayout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        effectiveRect = rect.adjusted(+left, +top, -right, -bottom)
        x = effectiveRect.x()
        y = effectiveRect.y()

        lineHeight = 0

        for item in self.itemList:
            widget = item.widget()
            spaceX = self.horizontalSpacing()
            if spaceX == -1:
                spaceX = widget.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton,
                                                      QtCore.Qt.Horizontal)
            spaceY = self.verticalSpacing()
            if spaceY == -1:
                spaceY = widget.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton,
                                                      QtCore.Qt.Vertical)

            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > effectiveRect.right() and lineHeight > 0:
                x = effectiveRect.x()
                y += lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y() + bottom

    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()
