from __future__ import annotations

import os
from typing import Union

from PIL import Image, ImageQt
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtSql
from PySide6 import QtWidgets as qtw

from library_of_h.explorer.constants import (BROWSER_IMAGES_LIMIT,
                                             THUMBNAIL_SIZE)
from library_of_h.explorer.custom_sub_classes.browser_items_delegate import \
    BrowserItemsDelegate
from library_of_h.explorer.custom_sub_classes.browser_items_model import \
    BrowserItemsModel
from library_of_h.explorer.database_manager import ExplorerDatabaseManager


class ImageBrowser(qtw.QListView):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._model = BrowserItemsModel(parent=self)

        self.setAlternatingRowColors(True)
        self.setItemDelegate(BrowserItemsDelegate(self))
        self.setModel(self._model)
        self.setSelectionMode(qtw.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(qtw.QListView.ScrollMode.ScrollPerPixel)

        self._worker = CreateItemWorker(parent=self)
        self._worker.item_created_signal.connect(self._add_item)

        self._database_manager = ExplorerDatabaseManager()

        self._initialize()

    def _initialize(self):
        self._database_manager.get(
            callback=self._create_items,
            limit=BROWSER_IMAGES_LIMIT,
        )

    def _create_items(self, results: list[Union[QtSql.QSqlRecord, None]]) -> None:
        self._worker.prepare(results)
        qtc.QThreadPool.globalInstance().start(self._worker.create_items)

    def _add_item(self, index: int, thumbnail: qtg.QImage, description: str):
        model_index = self._model.createIndex(index, 0)
        self._model.setData(model_index, thumbnail, qtc.Qt.ItemDataRole.DecorationRole)
        self._model.setData(model_index, description, qtc.Qt.ItemDataRole.DisplayRole)
        self.update(model_index)


class CreateItemWorker(qtc.QObject):

    item_created_signal = qtc.Signal(int, qtg.QImage, str)

    def _create_description(self, record: qtc.QSqlRecord) -> str:
        description = "\n".join(f"{i}this is text" for i in range(40))
        return description

    def _create_thumbnail(self, record: QtSql.QSqlRecord) -> qtg.QImage:
        location = record.value(record.indexOf("location"))
        file = os.path.join(location, sorted(os.listdir(location))[0])
        image = Image.open(file)
        if image.width > THUMBNAIL_SIZE[0] or image.height > THUMBNAIL_SIZE[0]:
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        source = image.toqimage()

        # Create a blank `QImage` with `THUMBNAIL_SIZE` dimensions:
        qimage = qtg.QImage(
            *THUMBNAIL_SIZE, source.format()
        )  # The maximum area for a thumbnail image.
        # Make it black.
        qimage.fill(qtc.Qt.GlobalColor.transparent)

        # Create a `QPainter` to draw on the blank `QImage`.
        temp_painter = qtg.QPainter(qimage)

        # Get the bounding box of the source image.
        image_rect = source.rect()  # The area of the actual thumbnail image.
        # Move the center of the bounding box of the source image to the center
        # of the bounding box of the blank `QImage`.
        image_rect.moveCenter(qimage.rect().center())
        # Now `image_rect`'s dimensions are the exact dimensions of the
        # source image if placed at the center of the thumbnail area.

        # Finally, draw the source image onto the thumbnail area using `image_rect`'s dimensions.
        temp_painter.drawImage(
            image_rect.topLeft(),  # The (x,y) co-ordinates for the start of `image_rect`
            source,
        )

        temp_painter.end()

        return qimage

    def create_items(self):
        for index, record in enumerate(self._records):
            thumbnail = self._create_thumbnail(record)
            description = self._create_description(record)
            self.item_created_signal.emit(index, thumbnail, description)

    def prepare(self, records: list[Union[QtSql.QSqlRecord, None]]) -> None:
        self._records = records
