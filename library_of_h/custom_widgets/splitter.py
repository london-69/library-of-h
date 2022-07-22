from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw


class SplitterHandle(qtw.QSplitterHandle):
    def __init__(self, o: qtc.Qt.Orientation, *args, **kwargs) -> None:
        super().__init__(o, *args, **kwargs)

        self._sizeof_1, self._sizeof_2 = 1, 0

    def mouseDoubleClickEvent(self, a0: qtg.QMouseEvent) -> None:
        super().mouseDoubleClickEvent(a0)
        self.collapse()

    def collapse(self) -> None:
        if self._sizeof_1 == 0:
            # If collapsed.
            self._sizeof_1 = self.parent().widget(0).maximumWidth()
            self._sizeof_2 = (
                self.parent().parent().width()
                - self._sizeof_1
                - self.parent().handleWidth()
            )
            self.parent().setSizes([self._sizeof_1, self._sizeof_2])
        else:
            self._sizeof_1 = 0
            self._sizeof_2 = (
                self.parent().parent().width() - self.parent().handleWidth()
            )
            self.parent().setSizes([self._sizeof_1, self._sizeof_2])


class Splitter(qtw.QSplitter):
    def createHandle(self) -> SplitterHandle:
        handle = SplitterHandle(self.orientation(), self)
        return handle
