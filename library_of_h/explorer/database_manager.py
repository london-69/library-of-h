from library_of_h.database_manager.main import DatabaseManagerBase


class ExplorerDatabaseManager:
    def __init__(self) -> None:
        self._database_manager = DatabaseManagerBase.get_instance()

    def __getattr__(self, attr: str):
        return getattr(self._database_manager, attr)
