from __future__ import annotations

import math
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


class ImageBrowser(qtw.QWidget):

    _current_page_number: int
    _current_query: dict

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.setLayout(qtw.QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self._database_manager = ExplorerDatabaseManager(parent=self)
        self._view = qtw.QListView(parent=self)
        self._model = BrowserItemsModel(parent=self._view)
        self._worker = CreateItemWorker(parent=self)

        self._view.setAlternatingRowColors(True)
        self._view.setItemDelegate(BrowserItemsDelegate(self._view))
        self._view.setModel(self._model)
        self._view.setSelectionMode(
            qtw.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._view.setVerticalScrollMode(qtw.QListView.ScrollMode.ScrollPerPixel)

        self._worker.item_created_signal.connect(self._add_item_slot)

        self._create_numbers_widgets()

        self.layout().addWidget(self._view, 0, 0, 1, 12)
        self.layout().addWidget(self._current_items_label, 1, 0, 1, 1)
        self.layout().addWidget(self._previous_page_button, 1, 4, 1, 1)
        self.layout().addWidget(self._page_number_line_edit, 1, 5, 1, 1)
        self.layout().addWidget(self._page_number_label, 1, 6, 1, 1)
        self.layout().addWidget(self._next_page_button, 1, 7, 1, 1)
        self.layout().addWidget(self._total_items_label, 1, 11, 1, 1)

        self._initialize()

    def _initialize(self):
        self._current_query = {}
        if not self._database_manager.get(
            count=True,
            get_callback=self._create_items,
            count_callback=self._update_numbers,
            limit=BROWSER_IMAGES_LIMIT,
            join="*",
        ):
            self._no_results()
        else:
            self._current_query["join"] = "*"
            self._update_page_number_line_edit(1)

    def _change_page(self, value):
        self._model.removeRows(0, self._model.rowCount())
        self._update_page_number_line_edit(value)
        offset = (self._current_page_number - 1) * BROWSER_IMAGES_LIMIT
        if not self._database_manager.get(
            count=True,
            get_callback=self._create_items,
            count_callback=self._update_numbers,
            limit=BROWSER_IMAGES_LIMIT,
            offset=offset,
            **self._current_query,
        ):
            self._no_results()

    def _create_numbers_widgets(self):
        self._current_items_label = qtw.QLabel("[0 - 0]", parent=self)
        self._current_items_label.setAlignment(
            qtc.Qt.AlignmentFlag.AlignLeft | qtc.Qt.AlignmentFlag.AlignVCenter
        )

        self._previous_page_button = qtw.QPushButton("Previous", parent=self)
        self._previous_page_button.clicked.connect(
            self._previous_page_button_clicked_slot
        )

        self._page_number_line_edit = qtw.QLineEdit("0", parent=self)
        self._page_number_line_edit.textChanged.connect(
            self._page_number_line_edit_text_changed_slot
        )
        self._page_number_line_edit.returnPressed.connect(
            self._page_number_line_edit_return_pressed_slot
        )
        self._page_number_line_edit.setFixedSize(44, 22)
        self._page_number_line_edit.setAlignment(qtc.Qt.AlignmentFlag.AlignCenter)

        self._page_number_label = qtw.QLabel("1", parent=self)
        self._page_number_label.setAlignment(qtc.Qt.AlignmentFlag.AlignCenter)
        self._page_number_label.setMaximumWidth(44)

        self._next_page_button = qtw.QPushButton("Next", parent=self)
        self._next_page_button.clicked.connect(self._next_page_button_clicked_slot)

        self._total_items_label = qtw.QLabel("0", parent=self)
        self._total_items_label.setAlignment(
            qtc.Qt.AlignmentFlag.AlignRight | qtc.Qt.AlignmentFlag.AlignVCenter
        )

    def _create_items(self, results: list[QtSql.QSqlRecord]) -> None:
        if not results:
            self._no_results()
            return
        self._worker.prepare(results)
        qtc.QThreadPool.globalInstance().start(self._worker.create_items)

    @property
    def _current_page_number(self):
        return self.__current_page_number

    @_current_page_number.setter
    def _current_page_number(self, page_number: int):
        self.__current_page_number = page_number
        if page_number == 1:
            self._previous_page_button.setDisabled(True)
        else:
            self._previous_page_button.setDisabled(False)

        if page_number == int(self._page_number_label.text()):
            self._next_page_button.setDisabled(True)
        else:
            self._next_page_button.setDisabled(False)

    def _no_results(self):
        self._total_items_label.setText("0")
        self._page_number_label.setText("1")
        self._current_items_label.setText("[0 - 0]")
        self._current_page_number = 1

    def _update_numbers(self, result: list[QtSql.QSqlRecord]):
        total_rows = result[0].value("total_rows")
        from_ = (
            (int(self._page_number_line_edit.text()) - 1) * BROWSER_IMAGES_LIMIT
        ) + 1
        to = min(total_rows, from_ + BROWSER_IMAGES_LIMIT - 1)
        self._total_items_label.setText(str(total_rows))
        self._page_number_label.setText(
            str(math.ceil(total_rows / BROWSER_IMAGES_LIMIT))
        )
        self._current_items_label.setText(f"[{from_} - {to}]")
        # To update disabled states of the buttons.
        self._current_page_number = self._current_page_number

    def _update_page_number_line_edit(self, value: int):
        max_page_number = int(self._page_number_label.text())
        current_page_number = (
            1 if value < 1 else max_page_number if value > max_page_number else value
        )
        self._page_number_line_edit.setText(str(current_page_number))
        self._current_page_number = current_page_number

    def filter(self, filter_string: str):
        self._model.removeRows(0, self._model.rowCount())
        if not self._database_manager.get(
            count=True,
            get_callback=self._create_items,
            count_callback=self._update_numbers,
            join="*",
            filter=filter_string,
            limit=BROWSER_IMAGES_LIMIT,
        ):
            self._no_results()
        else:
            self._current_query["join"] = "*"
            self._current_query["filter"] = filter_string
            self._update_page_number_line_edit(1)

    def _add_item_slot(self, index: int, thumbnail: qtg.QImage, description: str):
        model_index = self._model.createIndex(index, 0)
        self._model.setData(model_index, thumbnail, qtc.Qt.ItemDataRole.DecorationRole)
        self._model.setData(model_index, description, qtc.Qt.ItemDataRole.DisplayRole)
        self._view.update(model_index)

    def _next_page_button_clicked_slot(self):
        self._change_page(self._current_page_number + 1)

    def _page_number_line_edit_return_pressed_slot(self):
        text = self._page_number_line_edit.text()
        if not text:
            self._page_number_line_edit.setText(str(self._current_page_number))
        else:
            self._change_page(int(text))

    def _page_number_line_edit_text_changed_slot(self, text: str):
        if not text:
            return
        if text[-1] not in "0123456789":
            self._page_number_line_edit.setText(text[:-1])

    def _previous_page_button_clicked_slot(self):
        self._change_page(self._current_page_number - 1)


class CreateItemWorker(qtc.QObject):

    item_created_signal = qtc.Signal(int, qtg.QImage, str)

    def _create_description(self, record: qtc.QSqlRecord) -> str:
        description = "\n".join(f"{i}this is text" for i in range(40))
        return description

    def _create_thumbnail(self, record: QtSql.QSqlRecord) -> qtg.QImage:
        location = record.value("location")
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
