from typing import Union

from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw

from library_of_h.explorer.constants import (BROWSER_ITEMS_V_SPACING,
                                             SELECTION_TINT_WIDTH,
                                             THUMBNAIL_SIZE)


class DescriptionPlainTextEdit(qtw.QPlainTextEdit):

    timestamp: float = 0

    def wheelEvent(self, e: qtg.QWheelEvent):
        if (
            (
                self.verticalScrollBar().value() == self.verticalScrollBar().maximum()
                or self.verticalScrollBar().value()
                == self.verticalScrollBar().minimum()
            )
            and self.timestamp
            and e.timestamp() - self.timestamp > 500
        ):
            self.timestamp = 0
            e.ignore()
            return

        self.timestamp = e.timestamp()

        if abs(e.angleDelta().x()) > abs(e.angleDelta().y()):
            qtc.QCoreApplication.sendEvent(self.horizontalScrollBar(), e)
        else:
            qtc.QCoreApplication.sendEvent(self.verticalScrollBar(), e)

        e.accept()

        return


class BrowserItemsDelegate(qtw.QStyledItemDelegate):
    def createEditor(
        self,
        parent: qtw.QWidget,
        option: qtw.QStyleOptionViewItem,
        index: qtc.QModelIndex,
    ) -> qtw.QPlainTextEdit:
        editor = DescriptionPlainTextEdit(parent)
        editor.setReadOnly(True)
        return editor

    def paint(
        self,
        painter: qtg.QPainter,
        option: qtw.QStyleOptionViewItem,
        index: qtc.QModelIndex,
    ) -> None:
        option = self._get_option(option, index)
        if option.state & qtw.QStyle.StateFlag.State_Selected:
            painter.fillRect(
                qtc.QRect(
                    option.rect.left() - SELECTION_TINT_WIDTH,
                    option.rect.top(),
                    SELECTION_TINT_WIDTH,
                    option.rect.height(),
                ),
                qtc.Qt.GlobalColor.blue,
            )
        option.state &= ~qtw.QStyle.StateFlag.State_Selected
        widget = option.widget
        style = self._get_style(widget)

        style.drawControl(qtw.QStyle.CE_ItemViewItem, option, painter, widget)

    def setEditorData(self, editor: qtw.QPlainTextEdit, index: qtc.QModelIndex) -> None:
        description = index.model().data(index, qtc.Qt.ItemDataRole.DisplayRole)
        editor.setPlainText(description)

    def sizeHint(
        self, option: qtw.QStyleOptionViewItem, index: qtc.QModelIndex
    ) -> qtc.QSize:
        return qtc.QSize(500, THUMBNAIL_SIZE[1] + BROWSER_ITEMS_V_SPACING)

    def updateEditorGeometry(
        self,
        editor: qtw.QPlainTextEdit,
        option: qtw.QStyleOptionViewItem,
        index: qtc.QModelIndex,
    ) -> None:
        option = self._get_option(option, index)
        style = self._get_style(option)

        editor.setGeometry(style.subElementRect(qtw.QStyle.SE_ItemViewItemText, option))

    def _get_option(
        self, option: qtw.QStyleOptionViewItem, index: qtc.QModelIndex
    ) -> qtw.QStyleOptionViewItem:
        option = qtw.QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        option.rect = qtc.QRect(
            option.rect.left() + SELECTION_TINT_WIDTH,
            option.rect.top(),
            option.rect.width() - SELECTION_TINT_WIDTH,
            option.rect.height(),
        )
        option.decorationSize = qtc.QSize(*THUMBNAIL_SIZE)
        option.showDecorationSelected = True
        option.TextElideMode = qtc.Qt.TextElideMode.ElideRight
        return option

    def _get_style(
        self, arg__1: Union[qtw.QWidget, qtw.QStyleOptionViewItem]
    ) -> qtw.QStyle:
        if isinstance(arg__1, qtw.QStyleOptionViewItem):
            widget = arg__1.widget
        else:
            widget = arg__1
        style = widget.style() if widget else qtw.QApplication.style()
        return style
