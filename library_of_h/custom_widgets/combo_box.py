from PySide6 import QtCore as qtc
from PySide6 import QtWidgets as qtw


class ComboBox(qtw.QComboBox):
    def showPopup(self) -> None:
        super().showPopup()
        pos = self.mapToGlobal(
            qtc.QPoint(0, self.height())
        )  # Get global coordinates of 0, height() of this widget.
        self.view().parent().move(pos)  # Move view()'s parent() to said coordinates.
        # Not sure why we need to view().parent() instead of just view().
