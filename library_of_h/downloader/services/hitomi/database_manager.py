from PySide6 import QtCore as qtc

from library_of_h.database_manager.main import DatabaseManagerBase
from library_of_h.downloader.services.hitomi.metadata import \
    HitomiGalleryMetadata


class HitomiDatabaseManager:
    def __init__(self, *args, **kwargs) -> None:
        self._database_manager = DatabaseManagerBase.get_instance(*args, **kwargs)

    def __getattr__(self, attr: str):
        return getattr(self._database_manager, attr)

    def insert_into_table(self, gallery_metadata: HitomiGalleryMetadata) -> None:
        self._database_manager.insert_into_types(
            gallery_metadata.gallery_id, gallery_metadata.type_
        )
        self._database_manager.insert_into_sources(
            gallery_metadata.gallery_id, "hitomi"
        )

        self._database_manager.insert_into_galleries(
            gallery_id=gallery_metadata.gallery_id,
            title=gallery_metadata.title,
            japanese_title=gallery_metadata.japanese_title,
            upload_date=gallery_metadata.upload_date,
            pages=gallery_metadata.pages,
            location=gallery_metadata.location,
            type_=gallery_metadata.type_,
            source="hitomi",
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
            tag_sex = -1
            if "female:" in tag_name:
                tag_sex = 0
                tag_name = tag_name.replace("female:", "")
            elif "male:" in tag_name:
                tag_sex = 1
                tag_name = tag_name.replace("male:", "")
            self._database_manager.insert_into_tags(
                gallery_metadata.gallery_id, tag_name, tag_sex
            )
