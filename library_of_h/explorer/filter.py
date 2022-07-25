from PySide6 import QtCore as qtc
from PySide6 import QtWidgets as qtw


class Filter(qtw.QWidget):

    filter_button_clicked_signal = qtc.Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setLayout(qtw.QGridLayout())
        self.setGeometry(self.rect().x(), self.rect().y(), 396, 120)

        self._filter_line_edit = qtw.QLineEdit(self)
        self._filter_line_edit.returnPressed.connect(self._filter_button_clicked_slot)

        self._filter_button = qtw.QPushButton("Filter", self)
        self._filter_button.clicked.connect(self._filter_button_clicked_slot)
        self._filter_button.setFixedSize(111, 26)

        self.layout().addWidget(self._filter_line_edit, 0, 0, 1, 2)
        self.layout().addWidget(self._filter_button, 0, 2, 1, 1)

    def _filter_button_clicked_slot(self):
        self.filter_button_clicked_signal.emit(self._filter_line_edit.text())
