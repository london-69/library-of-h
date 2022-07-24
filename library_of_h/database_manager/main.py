import logging
import queue
import re
import sqlite3
from contextlib import contextmanager
from typing import Callable, Literal, Union
from weakref import proxy

from PySide6 import QtCore as qtc
from PySide6 import QtSql
from PySide6 import QtWidgets as qtw

from library_of_h.custom_widgets.progress_dialog import ProgressDialog
from library_of_h.database_manager.constants import (JOIN_MAPPING, LEN_QUERIES,
                                                     QUERIES, WHERE_MAPPING)
from library_of_h.logger import MainType, ServiceType, SubType, get_logger
from library_of_h.preferences import Preferences
from library_of_h.signals_hub.signals_hub import database_manager_signals


class DatabaseManagerBase(qtc.QObject):

    _instance = None

    _logger: logging.Logger

    _update_progress_dialog_signal = qtc.Signal()
    _write_thread_closed_signal = qtc.Signal()
    _read_operation_finished_signal = qtc.Signal(list, object)

    @classmethod
    def get_instance(cls):
        if cls._instance:
            return proxy(cls._instance)

        instance = super().__new__(cls)
        instance._initialize()
        cls._instance = instance
        return proxy(cls._instance)

    def __init__(self) -> None:
        raise RuntimeError("Use the classmethod 'get_instance' to get an instance.")

    def _initialize(self):
        super().__init__()

        self._logger = get_logger(
            main_type=MainType.DATABASE,
            service_type=ServiceType.NONE,
            sub_type=SubType.NONE,
        )

        self._queries_iter = iter(QUERIES)

        self._ands_pattern = re.compile('([-a-zA-Z]*?:".*?")')
        self._type_and_or_vals_pattern = re.compile(" *: *")
        self._or_vals_remove_quotes_pattern = re.compile('" *(.+) *"')
        self._or_vals_commas_pattern = re.compile(" *, *")

        self.write_query_queue = queue.Queue()
        self.read_query_queue = queue.Queue()

        directory = qtc.QDir(
            qtc.QDir.cleanPath(
                Preferences.get_instance()["database_preferences", "location"]
            )
        )
        if not directory.makeAbsolute():
            self._logger.error(
                f"Failed to makeAbsolute directory: LOCATION={directory}"
            )
            return
        if not directory.mkpath(directory.path()):
            self._logger.error(f"Failed to mkpath directory: LOCATION={directory}")
            return
        self._database_file_path = directory.absoluteFilePath("library_of_h.db")

        self._execute_pragma()
        self._create_tables_if_not_exist()

        qtc.QThreadPool.globalInstance().start(self._threaded_execute_write_queries)
        qtc.QThreadPool.globalInstance().start(self._threaded_execute_read_queries)

        self._update_progress_dialog_signal.connect(self._update_progress_dialog_slot)
        self._write_thread_closed_signal.connect(self._remove_databases)
        self._read_operation_finished_signal.connect(self._call_callback)

    def _call_callback(self, results: list[QtSql.QSqlRecord], callback: Callable):
        callback(results)

    def _create_progress_dialog(
        self,
        labelText: str,
        cancelButtonText: str,
        minimum: int,
        maximum: int,
        parent: qtw.QWidget = None,
        f: qtc.Qt.WindowType = qtc.Qt.WindowType.Dialog,
    ):
        if hasattr(self, "_progress_dialog"):
            return

        self._progress_dialog = ProgressDialog(
            labelText, cancelButtonText, minimum, maximum, parent, f
        )
        self._progress_dialog.setWindowTitle("Database progress")
        self._progress_dialog.show()

    def _create_tables_if_not_exist(self) -> None:
        QtSql.QSqlDatabase.addDatabase("QSQLITE", "create")
        QtSql.QSqlDatabase.database("create").setDatabaseName(self._database_file_path)
        self._create_progress_dialog(
            "Waiting on database create operations...", None, 0, LEN_QUERIES
        )
        if not (
            QtSql.QSqlDatabase.database("create").open()
            and QtSql.QSqlDatabase.database("create").transaction()
        ):
            self._logger.error(
                f"[{QtSql.QSqlDatabase.database('create').lastError().text()}] "
                f"Error opening database for create."
            )
        else:
            query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database("create"))
            for sql_query in QUERIES:
                query.prepare(sql_query)
                query.exec()
                self._update_progress_dialog_signal.emit()
            if not QtSql.QSqlDatabase.database("create").commit():
                self._logger.error(
                    f"[{QtSql.QSqlDatabase.database('write').lastError().text()}] "
                    f"Error commiting changes to database."
                )
            else:
                QtSql.QSqlDatabase.database("create").close()
                QtSql.QSqlDatabase.removeDatabase("create")
                self._delete_progress_dialog()

    def _delete_progress_dialog(self) -> None:
        if hasattr(self, "_progress_dialog"):
            # Don't need to self._progress_dialog.close() because the dialog is
            # closed when progress finishes.
            self._progress_dialog.deleteLater()
            del self._progress_dialog

    def _execute_pragma(self):
        QtSql.QSqlDatabase.addDatabase("QSQLITE", "PRAGMA")
        QtSql.QSqlDatabase.database("PRAGMA").setDatabaseName(self._database_file_path)
        QtSql.QSqlDatabase.database("PRAGMA").open()
        QtSql.QSqlQuery(
            "PRAGMA journal_mode=wal", QtSql.QSqlDatabase.database("PRAGMA")
        ).exec()
        QtSql.QSqlDatabase.database("PRAGMA").close()
        QtSql.QSqlDatabase.removeDatabase("PRAGMA")

    def _parse_filter_clause(
        self, filter_clause: str, comp: str
    ) -> tuple[str, str, list, list]:
        """
        Parses `filter_clause` string to create a valid SQL query.

        Parameters
        -----------
            filter_clause (str):
                A custom query that looks like 'key1:"value1, value2, ..." key2:"..." ...'
            comp (str):
                Comparision method for the query.

        Returns
        --------
        tuple[
            str:
                SQL WHERE clause for include queries.
            str:
                SQL WHERE clause for exclude queries.
            list:
                Bind values for the query/queries.
            list:
                Set of keys for `JOIN_MAPPING`, only used when `join` for `self.get`
                is "auto".
        ]
        """
        # Let filter_clause = 'artist:"name1, name2" -artist:"name3" language:"english" -language:"korean"'.
        # Let comp = '='.
        #
        # `ands` is a list of outer most WHERE clauses that are mutually exclusive;
        # 'key:"value(s)"' pairs in `filter_clause` are mutually excusive WHERE clauses.
        ands = self._ands_pattern.findall(
            filter_clause
        )  # ['artist:"name1, name2"', '-artist:"name3"', 'language:"english"', '-language:"korean"']

        bind_values = []  # Bind values to use with `QtSql.QSqlQuery` query.

        # Set of keys for `JOIN_MAPPING`, only used when `join` for `self.get` is
        # "auto". A set because there can be duplicates, example: "category" and
        # "-category".
        type_keys = set()

        include_vals = []  # Include data that match the values in result.
        exclude_vals = []  # Exclude data that match the values from result.

        for and_ in ands:
            # Let and_ = '-artist:"name3"'.
            #
            # type_ = "-artist", or_vals = '"name3"'
            type_, or_vals = self._type_and_or_vals_pattern.split(and_)

            try:
                # Remove ""s from the `or_vals` and split it on commas.
                or_vals = self._or_vals_commas_pattern.split(
                    self._or_vals_remove_quotes_pattern.search(or_vals)[1]
                )
            except TypeError:
                # `TypeError` means `filter_clause` was malformed in some way;
                # skip this `and_`
                continue

            if type_.startswith("-"):
                # `type_` starting with '-' indicates exclusion of matching records from result.
                type_keys.add(type_[1:])
                exclude_vals.append((type_[1:], or_vals))
            else:
                type_keys.add(type_)
                include_vals.append((type_, or_vals))

        include_query_logic = ""
        for type_, or_vals in include_vals:
            # Let type_ = "artist" and or_vals = ["name1", "name2"]
            try:
                type_ = WHERE_MAPPING[type_]
            except KeyError:
                # `KeyError` means `filter_clause` was malformed in some way;
                # skip this include val.
                continue

            bind_values.extend(or_vals)

            # '"Atrists"."artist_name"=? OR "Atrists"."artist_name"=?'
            or_query = f"{type_}{comp}{f' OR {type_}{comp}'.join('?' * len(or_vals))}"
            if not include_query_logic:
                # If `include_query_logic` is empty just add the query to it,
                include_query_logic += f"({or_query})"
            else:
                # Else add it as an AND clause.
                include_query_logic += " AND " f"({or_query})"

        exclude_query_logic = ""
        for type_, or_vals in exclude_vals:
            # Let type_ = "artist" and or_vals = ["name3"]
            try:
                type_ = WHERE_MAPPING[type_]
            except KeyError:
                # `KeyError` means `filter_clause` was malformed in some way;
                # skip this include val.
                continue

            bind_values.extend(or_vals)

            # '"Atrists"."artist_name"=?'
            or_query = f"{type_}{comp}{f' OR {type_}{comp}'.join('?' * len(or_vals))}"
            if not exclude_query_logic:
                # If `include_query_logic` is empty just add the query to it,
                exclude_query_logic += f"({or_query})"
            else:
                # Else add it as an AND clause.
                exclude_query_logic += " AND " f"({or_query})"

        if include_query_logic != "" or exclude_query_logic != "":
            return include_query_logic, exclude_query_logic, bind_values, type_keys
        else:
            return "", "", bind_values, type_keys

    def _read(self, query: QtSql.QSqlQuery) -> list:
        if not query.exec():
            self._logger.error(
                f"[{query.lastError().text()}] "
                f"Error reading from database: "
                f'Query="{query.lastQuery()}"'
            )
            self.read_query_queue = queue.Queue()  # Empty queue.
            return []

        model = QtSql.QSqlQueryModel()
        model.setQuery(query)

        results = [model.record(i) for i in range(model.rowCount())]

        return results

    @contextmanager
    def _read_context_manager(self, connection: str) -> None:
        try:
            if not QtSql.QSqlDatabase.database(connection).open():
                self._logger.error(
                    f"[Context Manager] Error opening database for read: "
                    + QtSql.QSqlDatabase.database(connection).lastError().text()
                )
            yield None
        finally:
            QtSql.QSqlDatabase.database(connection).close()

    def _remove_databases(self):
        QtSql.QSqlDatabase.removeDatabase("write")
        QtSql.QSqlDatabase.removeDatabase("read")

    def _threaded_execute_read_queries(self) -> None:
        QtSql.QSqlDatabase.addDatabase("QSQLITE", "read")
        QtSql.QSqlDatabase.database("read").setDatabaseName(self._database_file_path)

        while True:
            value = self.read_query_queue.get(block=True, timeout=None)
            with self._read_context_manager("read"):
                while True:
                    if value is None:
                        return
                    elif len(value) == 3:
                        query_str = value[0]
                        bind_values = value[1]
                        callback = value[2]
                    elif len(value) == 2:
                        query_str = value[0]
                        bind_values = ()
                        callback = value[1]

                    query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database("read"))
                    query.prepare(query_str)
                    for bind_value in bind_values:
                        query.addBindValue(bind_value, QtSql.QSql.ParamTypeFlag.Out)

                    self._read_operation_finished_signal.emit(
                        self._read(query), callback
                    )

                    try:
                        value = self.read_query_queue.get(block=False, timeout=None)
                    except queue.Empty:
                        break

                    query.clear()

    def _threaded_execute_write_queries(self) -> None:
        QtSql.QSqlDatabase.addDatabase("QSQLITE", "write")
        QtSql.QSqlDatabase.database("write").setDatabaseName(self._database_file_path)
        while True:
            value = self.write_query_queue.get(block=True, timeout=None)

            with self._write_context_manager("write"):
                query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database("write"))
                import time

                while True:
                    if isinstance(value, tuple):
                        query_str = value[0]
                        bind_values = value[1]

                    elif isinstance(value, str):
                        query_str = value
                        bind_values = ()

                    elif value is None:
                        self._delete_progress_dialog()
                        self._write_thread_closed_signal.emit()
                        return

                    query.prepare(query_str)
                    for bind_value in bind_values:
                        query.addBindValue(bind_value)
                    self._write(query)
                    try:
                        self._update_progress_dialog_signal.emit()
                    except AttributeError:
                        pass

                    try:
                        value = self.write_query_queue.get(block=False, timeout=None)
                    except queue.Empty:
                        break

                    query.clear()

    def _update_progress_dialog_slot(self) -> None:
        try:
            self._progress_dialog.update_progress()
        except AttributeError:
            # For when this is called when the progress dialog has not been
            # created.
            pass

    def _wait_for_database_operations(self):
        self._logger.info(
            f"Database manager has {self.write_query_queue.qsize()} pending write operations."
        )
        loop = qtc.QEventLoop()
        self._write_thread_closed_signal.connect(lambda: (print("ebedde"), loop.quit()))
        loop.exec()

    def _write(self, query: QtSql.QSqlQuery) -> None:
        if not query.exec():
            self._logger.error(
                f"[{query.lastError().text()}] "
                f"Error writing to database: "
                f'Query="{query.lastQuery()}"'
            )
            self.write_query_queue = queue.Queue()

    @contextmanager
    def _write_context_manager(self, connection: str) -> None:
        try:
            if not (
                QtSql.QSqlDatabase.database(connection).open()
                and QtSql.QSqlDatabase.database(connection).transaction()
            ):
                self._logger.error(
                    f"[Context Manager] Error opening database for write: "
                    + QtSql.QSqlDatabase.database(connection).lastError().text()
                )
            yield None
        finally:
            if not QtSql.QSqlDatabase.database(connection).commit():
                self._logger.error(
                    f"[Context Manager] Error commiting changes to database: "
                    + QtSql.QSqlDatabase.database(connection).lastError().text()
                )
            QtSql.QSqlDatabase.database(connection).close()

    @classmethod
    def clean_up(cls):
        instance = cls._instance
        if instance.write_query_queue.qsize() == instance.read_query_queue.qsize() == 0:
            instance.write_query_queue.put(None)
            instance.read_query_queue.put(None)
            return

        instance.write_query_queue.put(None)
        instance.read_query_queue.put(None)
        instance._create_progress_dialog(
            f"Waiting on {instance.write_query_queue.qsize() + instance.read_query_queue.qsize()} database operations...",
            None,
            0,
            instance.write_query_queue.qsize() + instance.read_query_queue.qsize(),
        )
        instance._wait_for_database_operations()

    def get(
        self,
        callback: Callable,
        select: Union[Literal["*"], list[str]] = "*",
        join: Union[Literal["auto"], Literal["*"], str, list[str]] = "",
        filter_clause: str = "",
        limit: int = 0,
        offset: int = 0,
    ) -> bool:
        """
        Queries the directory with provided arguments.

        Parameters
        -----------
            callback (Callable):
                Function to call when read operation ends.
            select (str):
                Which columns to select data from. Defaults to '*'.
            join (Union[Literal["auto"], Literal['*'], str, list[str]]):
                Table(s) to join. Defaults to ''. With "auto", join query is
                selected based on `filter_clause` keys.
            filter_clause (str):
                A custom query that looks like 'key1:"value1, value2, ..." key2:"..." ...'
            limit (int):
                Limit for maximum number of records to get.
            offset (int):
                Row offset to start getting records from. Defaults to 0.

        Returns
        --------
            bool:
                True:
                    An SQL query created based on the parameters was
                    successfully added to the read query queue.
                False:
                    No SQL query was created not added to the read query queue.
                    Denotes a syntax error in the passed `filter_clause`.
        """

        if isinstance(select, str):
            if select == "*":
                query_select = f"""SELECT DISTINCT {select} FROM "Galleries\""""
            else:
                query_select = f"""SELECT DISTINCT "{select}" FROM "Galleries\""""
        else:
            query_select = (
                f"""SELECT DISTINCT "{'","'.join(select)}" FROM "Galleries\""""
            )

        offset_limit_query = ""
        if limit:
            offset_limit_query = f"LIMIT {limit} OFFSET {offset}"

        if filter_clause == "":
            if join == "":
                query_join = ""
            elif join == "*" or join == "auto":
                query_join = "".join(value for value in JOIN_MAPPING.values())
            elif isinstance(join, str):
                query_join = JOIN_MAPPING[join]
            elif isinstance(join, list):
                query_join = "".join(JOIN_MAPPING[key] for key in join)

            query = "\n\n".join((query_select, query_join, offset_limit_query))

            self.read_query_queue.put((query, callback))
            return True

        comp_pref = Preferences.get_instance()["database_preferences"]["compare_like"]
        if comp_pref:
            comp = " LIKE "
        else:
            comp = "="

        (
            include_query_logic,
            exclude_query_logic,
            bind_values,
            type_keys,
        ) = self._parse_filter_clause(filter_clause=filter_clause, comp=comp)

        if join == "":
            query_join = ""
        elif isinstance(join, list):
            query_join = "".join(JOIN_MAPPING[key] for key in join)
        elif join == "*":
            query_join = "".join(value for value in JOIN_MAPPING.values())
        elif join == "auto":
            query_join = "".join(JOIN_MAPPING[key] for key in type_keys)
        elif isinstance(join, str):
            query_join = JOIN_MAPPING[join]
        elif isinstance(join, list):
            query_join = "".join(JOIN_MAPPING[key] for key in join)

        if not (include_query_logic or exclude_query_logic):
            return False

        elif include_query_logic and exclude_query_logic:
            # SELECT * FROM "Table"
            # JOIN (...)
            # WHERE (include)
            # AND "gallery_database_id" NOT IN (
            #   SELECT "gallery_database_id" FROM "Table"
            #   JOIN (...)
            #   WHERE (exclude)
            # )

            query = "\n\n".join(
                (
                    query_select,
                    query_join,
                    "WHERE",
                    include_query_logic,
                    'AND "gallery_database_id" NOT IN (',
                    'SELECT "gallery_database_id" FROM "Galleries"',
                    query_join,
                    "WHERE",
                    exclude_query_logic,
                    ")",
                    offset_limit_query,
                )
            )

        elif include_query_logic:
            query = "\n\n".join(
                (
                    query_select,
                    query_join,
                    "WHERE",
                    include_query_logic,
                    offset_limit_query,
                )
            )

        elif exclude_query_logic:
            query = "\n\n".join(
                (
                    query_select,
                    "WHERE",
                    '"gallery_database_id" NOT IN (',
                    'SELECT "gallery_database_id" FROM "Galleries"',
                    query_join,
                    "WHERE",
                    exclude_query_logic,
                    ")",
                    offset_limit_query,
                )
            )
        self.read_query_queue.put((query, bind_values, callback))
        return True

    def insert_into_artists(self, gallery_id: int, artist_name: str) -> None:
        artist_name = artist_name.lower()
        query = 'INSERT OR IGNORE INTO "Artists" ("artist_name") VALUES (?)'
        bind_values = (artist_name,)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Artist_Gallery" ("artist", "gallery")
            SELECT
            "artist_id", "gallery_database_id"
            FROM
            "Artists", "Galleries"
            WHERE
            "Artists"."artist_name" = ? AND "Galleries"."gallery_id" = ?
            """

        bind_values = (artist_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_characters(self, gallery_id: int, character_name: str) -> None:
        character_name = character_name.lower()
        query = 'INSERT OR IGNORE INTO "Characters" ("character_name") VALUES (?)'
        bind_values = (character_name,)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Character_Gallery"
            ("character", "gallery")
            SELECT
            "character_id", "gallery_database_id"
            FROM
            "Characters", "Galleries"
            WHERE
            "Characters"."character_name" = ? AND "Galleries"."gallery_id" = ?
            """
        bind_values = (character_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_galleries(
        self,
        gallery_id: int,
        title: str,
        japanese_title: str,
        upload_date: str,
        pages: int,
        location: str,
        type_: int,
        source: int,
    ) -> None:
        query = """
            INSERT OR IGNORE INTO "Galleries"
            (
                "gallery_id",
                "title",
                "japanese_title",
                "upload_date",
                "pages",
                "location",
                "type",
                "source"
            )
            SELECT ?, ?, ?, ?, ?, ?, "type_id", "source_id"
            FROM
            "Types", "Sources"
            WHERE
            "Types"."type_name" = ? AND "Sources"."source_name" = ?
            """
        bind_values = (
            gallery_id,
            title,
            japanese_title,
            upload_date,
            pages,
            location,
            type_,
            source,
        )
        self.write_query_queue.put((query, bind_values))

    def insert_into_groups(self, gallery_id: int, group_name: str) -> None:
        group_name = group_name.lower()
        query = 'INSERT OR IGNORE INTO "Groups" ("group_name") VALUES (?)'
        bind_values = (group_name,)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Group_Gallery"
            ("group", "gallery")
            SELECT
            "group_id", "gallery_database_id"
            FROM
            "Groups", "Galleries"
            WHERE
            "Groups"."group_name" = ? AND "Galleries"."gallery_id" = ?
            """
        bind_values = (group_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_languages(self, gallery_id: int, language_name: str) -> None:
        language_name = language_name.lower()
        query = 'INSERT OR IGNORE INTO "Languages" ("language_name") VALUES (?)'
        bind_values = (language_name,)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Language_Gallery"
            ("language", "gallery")
            SELECT
            "language_id", "gallery_database_id"
            FROM
            "Languages", "Galleries"
            WHERE
            "Languages"."language_name" = ? AND "Galleries"."gallery_id" = ?
            """
        bind_values = (language_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_series(self, gallery_id: int, series_name: str) -> None:
        series_name = series_name.lower()
        query = 'INSERT OR IGNORE INTO "Series" ("series_name") VALUES (?)'
        bind_values = (series_name,)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Series_Gallery"
            ("series", "gallery")
            SELECT
            "series_id", "gallery_database_id"
            FROM
            "Series", "Galleries"
            WHERE
            "Series"."series_name" = ? AND "Galleries"."gallery_id" = ?
            """
        bind_values = (series_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_sources(self, gallery_id: int, source_name: str) -> None:
        source_name = source_name.lower()
        query = 'INSERT OR IGNORE INTO "Sources" ("source_name") VALUES (?)'
        bind_values = (source_name,)
        self.write_query_queue.put((query, bind_values))

    def insert_into_tags(self, gallery_id: int, tag_name: str, tag_sex: int) -> None:
        tag_name = tag_name.lower()
        query = 'INSERT OR IGNORE INTO "Tags" ("tag_name", "tag_sex") VALUES (?, ?)'
        bind_values = (tag_name, tag_sex)
        self.write_query_queue.put((query, bind_values))

        query = f"""
            INSERT OR IGNORE INTO "Tag_Gallery"
            ("tag", "gallery")
            SELECT
            "tag_id", "gallery_database_id"
            FROM
            "Tags", "Galleries"
            WHERE
            "Tags"."tag_name" = ? AND "Galleries"."gallery_id" = ?
            """
        bind_values = (tag_name, gallery_id)
        self.write_query_queue.put((query, bind_values))

    def insert_into_types(self, gallery_id: int, type_name: str) -> None:
        type_name = type_name.lower()
        query = 'INSERT OR IGNORE INTO "Types" ("type_name") VALUES (?)'
        bind_values = (type_name,)
        self.write_query_queue.put((query, bind_values))
