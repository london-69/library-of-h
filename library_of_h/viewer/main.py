import os
from typing import Optional

from PIL import Image, ImageQt
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw


class CustomScrollArea(qtw.QScrollArea):

    RESIZED_CONSTANT = 10
    SCROLL_CONSTANT = 100

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._scroll_value = self.verticalScrollBar().minimum()
        self._control_modifier_state = False

    def _control_modifier_slot(self, state: bool) -> None:
        self._control_modifier_state = state

    def wheelEvent(self, event) -> None:
        if self._control_modifier_state:
            if event.angleDelta().y() == 120:
                self._resized += self.RESIZED_CONSTANT
                if self._resized >= 90:
                    self._resized = 90
                self._resize_image()
                self._image_label.setPixmap(self._current_image_pixmap)
            elif event.angleDelta().y() == -120:
                self._resized -= self.RESIZED_CONSTANT
                if self._resized <= -90:
                    self._resized = -90
                self._resize_image()
                self._image_label.setPixmap(self._current_image_pixmap)
        else:
            self._scroll(event.angleDelta().y())

    def _scroll(self, y) -> None:
        if y == -120:
            if (
                self._scroll_value + self.SCROLL_CONSTANT
                >= self.verticalScrollBar().maximum()
            ):
                self._scroll_value = self.verticalScrollBar().maximum()
            else:
                self._scroll_value += self.SCROLL_CONSTANT
        elif y == 120:
            if (
                self._scroll_value - self.SCROLL_CONSTANT
                <= self.verticalScrollBar().minimum()
            ):
                self._scroll_value = self.verticalScrollBar().minimum()
            else:
                self._scroll_value -= self.SCROLL_CONSTANT
        self.verticalScrollBar().setValue(self._scroll_value)


class Viewer(CustomScrollArea):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._resized = 0
        self._image_label = qtw.QLabel(
            alignment=qtc.Qt.AlignmentFlag.AlignCenter, objectName="MW_Label"
        )
        self.setWidget(self._image_label)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(qtc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(qtc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setFocusPolicy(qtc.Qt.FocusPolicy.NoFocus)
