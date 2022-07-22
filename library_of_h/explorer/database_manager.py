from PySide6 import QtCore as qtc

from library_of_h.database_manager.main import DatabaseManagerBase


class ExplorerDatabaseManager(DatabaseManagerBase):

    read_operation_finished_signal = qtc.Signal(list)
