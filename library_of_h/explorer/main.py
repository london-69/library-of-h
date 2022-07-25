from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw

from library_of_h.explorer.filter import Filter
from library_of_h.explorer.image_browser import ImageBrowser


class Explorer(qtw.QWidget):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setLayout(qtw.QVBoxLayout())

        self._create_filter()
        self._create_image_browser()

        self._filter.filter_button_clicked_signal.connect(self._image_browser.filter)

        self.layout().addWidget(self._filter)
        self.layout().addWidget(self._image_browser)

    def _create_filter(self) -> None:
        self._filter = Filter()
        self._filter.setFixedHeight(45)

    def _create_image_browser(self) -> None:
        self._image_browser = ImageBrowser()

    def createHandle(self) -> qtw.QSplitterHandle:
        handle = super().createHandle()
        handle.setLayout(qtw.QVBoxLayout())
        handle.layout().addWidget(qtw.QLabel("This is handle."))
        return handle
