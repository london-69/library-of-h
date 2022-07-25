from PySide6 import QtCore as qtc

from library_of_h.database_manager.main import DatabaseManagerBase
from library_of_h.downloader.services.nhentai.metadata import \
    nhentaiGalleryMetadata


class nhentaiDatabaseManager:
    def __init__(self, *args, **kwargs) -> None:
        self._database_manager = DatabaseManagerBase.get_instance(*args, **kwargs)

    def __getattr__(self, attr: str):
        return getattr(self._database_manager, attr)

    def _insert_into_nhentai_media_id(self, gallery_id: int, media_id: str) -> None:
        query = f"""
            INSERT OR IGNORE INTO "nhentaiMediaID_Gallery"
            ("media_id", "gallery")
            SELECT
            ?, "gallery_database_id"
            FROM
            "Galleries"
            WHERE
            "Galleries"."gallery_id" = ?
            """
        bind_values = (media_id, gallery_id)
        self._database_manager.write_query_queue.put((query, bind_values))

    def insert_into_table(self, gallery_metadata: nhentaiGalleryMetadata) -> None:
        self._database_manager.insert_into_types(
            gallery_metadata.gallery_id, gallery_metadata.type_
        )

        self._database_manager.insert_into_sources(
            gallery_metadata.gallery_id, "nhentai"
        )

        self._database_manager._insert_into_nhentai_media_id(
            gallery_metadata.gallery_id, gallery_metadata.media_id
        )

        self._database_manager.insert_into_galleries(
            gallery_id=gallery_metadata.gallery_id,
            title=gallery_metadata.title,
            japanese_title=gallery_metadata.japanese_title,
            upload_date=gallery_metadata.upload_date,
            pages=gallery_metadata.pages,
            location=gallery_metadata.location,
            type_=gallery_metadata.type_,
            source="nhentai",
        )

        for artist_name in gallery_metadata.artists:
            self._database_manager.insert_into_artists(
                gallery_metadata.gallery_id, artist_name
            )

        for character_name in gallery_metadata.characters:
            self._database_manager.insert_into_characters(
                gallery_metadata.gallery_id, character_name
            )

        for group_name in gallery_metadata.groups:
            self._database_manager.insert_into_groups(
                gallery_metadata.gallery_id, group_name
            )

        self._database_manager.insert_into_languages(
            gallery_metadata.gallery_id, gallery_metadata.language
        )

        for series_name in gallery_metadata.series:
            self._database_manager.insert_into_series(
                gallery_metadata.gallery_id, series_name
            )

        for tag_name in gallery_metadata.tags:
            self._database_manager.insert_into_tags(
                gallery_metadata.gallery_id, tag_name, -1
            )
