from typing import Any, NamedTuple, Optional, TypeVar, Union

from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw

from library_of_h.explorer.constants import BROWSER_IMAGES_LIMIT


class RowData(NamedTuple):
    thumbnail: qtg.QImage
    description: str


class ListData(NamedTuple):
    thumbnails: list[qtg.QImage]
    descriptions: list[str]


class BrowserItemsModel(qtc.QAbstractListModel):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._data = ListData(
            [None for _ in range(BROWSER_IMAGES_LIMIT)],
            [None for _ in range(BROWSER_IMAGES_LIMIT)],
        )

    def data(
        self, index: qtc.QModelIndex, role: qtc.Qt.ItemDataRole
    ) -> Union[int, None]:
        if not index.isValid():
            return None

        if role == qtc.Qt.ItemDataRole.DisplayRole:
            return self._data.descriptions[index.row()]
        elif role == qtc.Qt.ItemDataRole.DecorationRole:
            return self._data.thumbnails[index.row()]
        else:
            return None

    def flags(self, index) -> qtc.Qt.ItemFlag:
        return (
            qtc.Qt.ItemFlag.ItemIsEditable
            | qtc.Qt.ItemFlag.ItemIsEnabled
            | qtc.Qt.ItemFlag.ItemIsSelectable
        )

    def setData(
        self,
        index: qtc.QModelIndex,
        value: Union[qtg.QImage, str],
        role: qtc.Qt.ItemDataRole,
    ) -> None:
        if not index.isValid():
            return False

        if role == qtc.Qt.ItemDataRole.DisplayRole:
            self._data.descriptions[index.row()] = value
        elif role == qtc.Qt.ItemDataRole.DecorationRole:
            self._data.thumbnails[index.row()] = value
        else:
            return False

        self.dataChanged.emit(index, index, [role])
        return True

    def rowCount(self, _: Optional[qtc.QModelIndex] = None) -> int:
        return len(self._data.thumbnails) - self._data.thumbnails.count(None)
