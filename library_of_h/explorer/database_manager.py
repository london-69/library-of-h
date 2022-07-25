from library_of_h.database_manager.main import DatabaseManagerBase


class ExplorerDatabaseManager:
    def __init__(self, *args, **kwargs) -> None:
        self._database_manager = DatabaseManagerBase.get_instance(*args, **kwargs)

    def __getattr__(self, attr: str):
        return getattr(self._database_manager, attr)
