import logging
import queue
import re
import sqlite3
from contextlib import contextmanager
from typing import Literal, Union
from weakref import proxy

from PySide6 import QtCore as qtc
from PySide6 import QtSql
from PySide6 import QtWidgets as qtw

from library_of_h.custom_widgets.progress_dialog import ProgressDialog
from library_of_h.database_manager.constants import (JOIN_MAPPING, LEN_QUERIES,
                                                     QUERIES, WHERE_MAPPING)
from library_of_h.preferences import Preferences
from library_of_h.signals_hub.signals_hub import database_manager_signals


class DatabaseManagerBase(qtc.QObject):

    _instances = []

    _instance_number: int
    _logger: logging.Logger
    read_operation_finished_signal: "qtc.Signal(list)"

    _update_progress_dialog_signal = qtc.Signal()
    write_thread_closed_signal = qtc.Signal()

    def __new__(cls):
        instance = super().__new__(cls)
        cls._instances.append(instance)
        instance._instance_number = len(cls._instances)
        return proxy(instance)

    def __init__(self) -> None:
        super().__init__()

        self._queries_iter = iter(QUERIES)

        self._ands_pattern = re.compile('([-a-zA-Z]*?:".*?")')
        self._type_and_or_vals_pattern = re.compile(" *: *")
        self._or_vals_remove_quotes_pattern = re.compile('" *(.+) *"')
        self._or_vals_commas_pattern = re.compile(" *, *")

        self.write_query_queue = queue.Queue()
        self.read_query_queue = queue.Queue()

        self._create_table_if_not_exists_timer = qtc.QTimer()
        self._create_table_if_not_exists_timer.setSingleShot(True)
        self._create_table_if_not_exists_timer.timeout.connect(
            self._create_tables_if_not_exist_exec
        )

        self._update_progress_dialog_signal.connect(self._update_progress_dialog_slot)

        directory = qtc.QDir(
            qtc.QDir.cleanPath(
                Preferences.get_instance()["database_preferences", "location"]
            )
        )
        if not directory.makeAbsolute():
            self._logger.error(
                f"Failed to makeAbsolute directory: LOCATION={directory}"
            )
        if not directory.mkpath(directory.path()):
            self._logger.error(f"Failed to mkpath directory: LOCATION={directory}")
        self._file_path = directory.absoluteFilePath("library_of_h.db")

        QtSql.QSqlDatabase.addDatabase("QSQLITE", f"{self._instance_number}_PRAGMA")
        QtSql.QSqlDatabase.database(f"{self._instance_number}_PRAGMA").setDatabaseName(self._file_path)
        QtSql.QSqlDatabase.database(f"{self._instance_number}_PRAGMA").open()
        QtSql.QSqlQuery(
            "PRAGMA journal_mode=wal", QtSql.QSqlDatabase.database(f"{self._instance_number}_PRAGMA")
        ).exec()
        QtSql.QSqlDatabase.database(f"{self._instance_number}_PRAGMA").close()
        QtSql.QSqlDatabase.removeDatabase(f"{self._instance_number}_PRAGMA")

        qtc.QThreadPool.globalInstance().start(self._threaded_execute_write_queries)
        qtc.QThreadPool.globalInstance().start(self._threaded_execute_read_queries)

    def __del__(self) -> None:
        self._logger.debug(f"{type(self).__name__} instance deleted.")

    def _create_tables_if_not_exist_exec(self) -> None:
        query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database(f"{self._instance_number}_write_1"))
        try:
            query.exec(next(self._queries_iter))
        except StopIteration:
            if not QtSql.QSqlDatabase.database(f"{self._instance_number}_write_1").commit():
                self._logger.error(
                    f"[{QtSql.QSqlDatabase.database('write_1').lastError().text()}] "
                    f"Error commiting changes to database."
                )
            else:
                QtSql.QSqlDatabase.database(f"{self._instance_number}_write_1").close()
                QtSql.QSqlDatabase.removeDatabase(f"{self._instance_number}_write_1")
                self._create_table_if_not_exists_timer.stop()
                self._create_table_if_not_exists_timer.deleteLater()
                del self._create_table_if_not_exists_timer
                self._delete_progress_dialog()
                database_manager_signals.create_table_if_not_exists_finished_signal.emit()
        else:
            self._update_progress_dialog_signal.emit()
            self._create_table_if_not_exists_timer.start(0)

    def _delete_progress_dialog(self) -> None:
        if hasattr(self, "_progress_dialog"):
            # Don't need to self._progress_dialog.close() because the dialog is
            # closed when progress finishes.
            self._progress_dialog.deleteLater()
            del self._progress_dialog

    def _insert_into_artists(self, gallery_id: int, artist_name: str) -> None:
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

    def _insert_into_characters(self, gallery_id: int, character_name: str) -> None:
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

    def _insert_into_galleries(
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

    def _insert_into_groups(self, gallery_id: int, group_name: str) -> None:
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

    def _insert_into_languages(self, gallery_id: int, language_name: str) -> None:
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

    def _insert_into_series(self, gallery_id: int, series_name: str) -> None:
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

    def _insert_into_sources(self, gallery_id: int, source_name: str) -> None:
        source_name = source_name.lower()
        query = 'INSERT OR IGNORE INTO "Sources" ("source_name") VALUES (?)'
        bind_values = (source_name,)
        self.write_query_queue.put((query, bind_values))

    def _insert_into_tags(self, gallery_id: int, tag_name: str, tag_sex: int) -> None:
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

    def _insert_into_types(self, gallery_id: int, type_name: str) -> None:
        type_name = type_name.lower()
        query = 'INSERT OR IGNORE INTO "Types" ("type_name") VALUES (?)'
        bind_values = (type_name,)
        self.write_query_queue.put((query, bind_values))

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

    def _parse_filter_dict(
        self, filter_dict: dict, comp: str
    ) -> tuple[str, str, list, list]:
        """
        Creates a `filter_clause` with `user_dict` and passes that to
        `self._parse_filter_clause`.

        Parameters
        -----------
            filter_dict (dict):
                Dictionary mapping of filter category and keywords:
                    {
                        "key": {
                            "include": "comma separated values"
                            "exclude": "comma separated values"
                        }
                    }
            comp (str):
                Comparision method for the query.

        Returns
        --------
            See `self._parse_filter_clause`.
        """
        filter_mapping = {}
        # Creates a mapping of {"category": "values"} or {"-category: "values"} from
        # `filter_dict`:
        # {
        # "artist": {
        #       ...
        #   },
        # "-artist" : {
        #       ...
        #   }
        # }
        for category, values in filter_dict.items():
            for type_, vals in values.items():
                if type_ == "include":
                    filter_mapping.setdefault(category, [])
                    filter_mapping[category].extend(vals)
                if type_ == "exclude":
                    filter_mapping.setdefault(f"-{category}", [])
                    filter_mapping[f"-{category}"].extend(vals)

        filter_clause = ""
        # Create a user query with `filter_mapping`.
        for category, values in filter_mapping.items():
            filter_clause += f"{category}:\"{','.join(values)}\" "

        return parse_filter_clause(filter_clause, comp)

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

    def _threaded_execute_read_queries(self) -> None:
        QtSql.QSqlDatabase.addDatabase("QSQLITE", f"{self._instance_number}_read")
        QtSql.QSqlDatabase.database(f"{self._instance_number}_read").setDatabaseName(self._file_path)

        while True:
            value = self.read_query_queue.get(block=True, timeout=None)

            with self._read_context_manager(f"{self._instance_number}_read"):
                query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database(f"{self._instance_number}_read"))
                while True:
                    if isinstance(value, tuple):
                        query_str = value[0]
                        bind_values = value[1]
                    elif isinstance(value, str):
                        query_str = value
                        bind_values = ()
                    elif value is None:
                        try:
                            self.read_operation_finished_signal.disconnect()
                        except TypeError:
                            # TypeError: disconnect() failed between
                            # 'read_operation_finished_signal' and all its
                            # connections
                            pass
                        return

                    query.prepare(query_str)
                    for bind_value in bind_values:
                        query.addBindValue(bind_value, QtSql.QSql.ParamTypeFlag.Out)

                    self.read_operation_finished_signal.emit(self._read(query))

                    try:
                        value = self.read_query_queue.get(block=False, timeout=None)
                    except queue.Empty:
                        break

                    query.clear()

    def _threaded_execute_write_queries(self) -> None:
        QtSql.QSqlDatabase.addDatabase("QSQLITE", f"{self._instance_number}_write_2")
        QtSql.QSqlDatabase.database(f"{self._instance_number}_write_2").setDatabaseName(self._file_path)

        while True:
            value = self.write_query_queue.get(block=True, timeout=None)

            with self._write_context_manager(f"{self._instance_number}_write_2"):
                query = QtSql.QSqlQuery(QtSql.QSqlDatabase.database(f"{self._instance_number}_write_2"))
                while True:
                    if isinstance(value, tuple):
                        query_str = value[0]
                        bind_values = value[1]

                    elif isinstance(value, str):
                        query_str = value
                        bind_values = ()

                    elif value is None:
                        self._delete_progress_dialog()
                        self.write_thread_closed_signal.emit()
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

    def check_gallery_existence(self, gallery_id: int) -> bool:
        query = """SELECT "gallery_id" FROM "Galleries" WHERE "gallery_id" = ?"""
        bind_values = (gallery_id,)
        self.read_query_queue.put((query, bind_values))

    def clean_up(self):
        self._database_manager.write_query_queue.put(None)
        self._database_manager.read_query_queue.put(None)
        QtSql.QSqlDatabase.removeDatabase(f"{self._instance_number}_write_1")
        QtSql.QSqlDatabase.removeDatabase(f"{self._instance_number}_write_2")
        QtSql.QSqlDatabase.removeDatabase(f"{self._instance_number}_read")
        self.deleteLater()

    def create_progress_dialog(
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

    def create_tables_if_not_exist(self) -> None:
        self.create_progress_dialog(
            "Waiting on database write operations...", None, 0, LEN_QUERIES
        )
        if not (
            QtSql.QSqlDatabase.database(f"{self._instance_number}_write_1").open()
            and QtSql.QSqlDatabase.database(f"{self._instance_number}_write_1").transaction()
        ):
            self._logger.error(
                f"[{QtSql.QSqlDatabase.database('write_1').lastError().text()}] "
                f"Error opening database for write."
            )
        else:
            self._create_table_if_not_exists_timer.start(0)

    def get(
        self,
        filter_clause: str = "",
        select: Union[Literal["*"], list[str]] = "*",
        join: Union[Literal["auto"], Literal["*"], str, list[str]] = "",
        limit: int = 0,
        offset: int = 0,
        filter_dict: dict = {},
    ) -> bool:
        """
        Queries the directory with provided arguments.

        Parameters
        -----------
            filter_clause (str):
                A custom query that looks like 'key1:"value1, value2, ..." key2:"..." ...'
            select (str):
                Which columns to select data from. Defaults to '*'.
            join (Union[Literal["auto"], Literal['*'], str, list[str]]):
                Table(s) to join. Defaults to ''. With "auto", join query is
                selected based on `filter_clause` or `filter_dict` keys.
            limit (int):
                Limit for maximum number of records to get.
            offset (int):
                Row offset to start getting records from. Defaults to 0.
            filter_dict (dict):
                Dictionary mapping of filter category and keywords:
                    {
                        "key": {
                            "include": "comma separated values"
                            "exclude": "comma separated values"
                        }
                    }

        Returns
        --------
            bool:
                True:
                    An SQL query created based on the parameters was
                    successfully added to the read query queue.
                False:
                    No SQL query was created not added to the read query queue.
                    Denotes a syntax error in the passed `filter_clause`.
                    Not `filter_dict` because it ''should'' be passed a curated
                    dictionary.
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

        if not filter_clause and not filter_dict:
            if join == "":
                query_join = ""
            elif join == "*" or join == "auto":
                query_join = "".join(value for value in JOIN_MAPPING.values())
            elif isinstance(join, str):
                query_join = JOIN_MAPPING[join]
            elif isinstance(join, list):
                query_join = "".join(JOIN_MAPPING[key] for key in join)

            query = "\n\n".join((query_select, query_join, offset_limit_query))

            self.read_query_queue.put(query)
            return True

        comp_pref = Preferences.get_instance()["database_preferences"]["compare_like"]
        if comp_pref:
            comp = " LIKE "
        else:
            comp = "="

        if filter_clause != "":
            (
                include_query_logic,
                exclude_query_logic,
                bind_values,
                type_keys,
            ) = parse_filter_clause(filter_clause=filter_clause, comp=comp)
        else:
            (
                include_query_logic,
                exclude_query_logic,
                bind_values,
                type_keys,
            ) = parse_filter_dict(filter_dict=filter_dict, comp=comp)

        if isinstance(join, list):
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
        self.read_query_queue.put((query, bind_values))
        return True