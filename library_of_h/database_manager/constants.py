JOIN_MAPPING = {
    "artist": """\
JOIN "Artist_Gallery" ON "Artist_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Artists" ON "Artist_Gallery"."artist"="Artists"."artist_id"
""",
    "character": """\
JOIN "Character_Gallery" ON "Character_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Characters" ON "Character_Gallery"."character"="Characters"."character_id"
""",
    "group": """\
JOIN "Group_Gallery" ON "Group_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Groups" ON "Group_Gallery"."group"="Groups"."group_id"
""",
    "language": """\
JOIN "Language_Gallery" ON "Language_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Languages" ON "Language_Gallery"."language"="Languages"."language_id"
""",
    "series": """\
JOIN "Series_Gallery" ON "Series_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Series" ON "Series_Gallery"."series"="Series"."series_id"
""",
    "tag": """\
JOIN "Tag_Gallery" ON "Tag_Gallery"."gallery"="Galleries"."gallery_database_id"
JOIN "Tags" ON "Tag_Gallery"."tag"="Tags"."tag_id"
""",
    "type": """\
JOIN "Types" ON "Types"."type_id"="Galleries"."type"
""",
    "source": """\
JOIN "Sources" ON "Sources"."source_id"="Galleries"."source"
""",
}

QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS "Artists"(
        "artist_id" INTEGER PRIMARY KEY,
        "artist_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Characters"(
        "character_id" INTEGER PRIMARY KEY,
        "character_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Groups"(
        "group_id" INTEGER PRIMARY KEY,
        "group_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Languages"(
        "language_id" INTEGER PRIMARY KEY,
        "language_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Series"(
        "series_id" INTEGER PRIMARY KEY,
        "series_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Sources"(
        "source_id" INTEGER PRIMARY KEY,
        "source_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Tags"(
        "tag_id" INTEGER PRIMARY KEY,
        "tag_name" TEXT NOT NULL,
        "tag_sex" INTEGER NULL,
        UNIQUE("tag_name", "tag_sex")
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Types"(
        "type_id" INTEGER PRIMARY KEY,
        "type_name" TEXT UNIQUE NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Artist_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "artist" INTEGER,
        "gallery" INTEGER,

        UNIQUE("artist", "gallery"),
        
        FOREIGN KEY("artist") REFERENCES "Artists"("artist_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Character_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "character" INTEGER,
        "gallery" INTEGER,

        UNIQUE("character", "gallery"),
        
        FOREIGN KEY("character") REFERENCES "Characters"("character_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Group_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "group" INTEGER,
        "gallery" INTEGER,

        UNIQUE("group", "gallery"),
        
        FOREIGN KEY("group") REFERENCES "Groups"("group_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Language_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "language" INTEGER,
        "gallery" INTEGER,

        UNIQUE("language", "gallery"),
        
        FOREIGN KEY("language") REFERENCES "Languages"("language_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Series_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "series" INTEGER,
        "gallery" INTEGER,

        UNIQUE("series", "gallery"),
        
        FOREIGN KEY("series") REFERENCES "Series"("series_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Tag_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "tag" INTEGER,
        "gallery" INTEGER,

        UNIQUE("tag", "gallery"),
        
        FOREIGN KEY("tag") REFERENCES "Tags"("tag_id") ON DELETE CASCADE,
        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "nhentaiMediaID_Gallery"(
        "id" INTEGER PRIMARY KEY,
        "media_id" INTEGER,
        "gallery" INTEGER,

        UNIQUE("media_id", "gallery"),

        FOREIGN KEY("gallery") REFERENCES "Galleries"("gallery_database_id") ON DELETE CASCADE
    )""",
    """
    CREATE TABLE IF NOT EXISTS "Galleries"(
    "gallery_database_id" INTEGER PRIMARY KEY,
    "source" INTEGER,
    "gallery_id" INTEGER NULL,
    "title" TEXT NULL,
    "japanese_title" TEXT NULL,
    "type" INTEGER NULL,
    "upload_date" TEXT NULL,
    "pages" INTEGER NULL,
    "location" TEXT NOT NULL,

    UNIQUE("source", "gallery_id"),

    FOREIGN KEY("source") REFERENCES "Sources"("source_id") ON DELETE CASCADE,
    FOREIGN KEY("type") REFERENCES "Types"("type_id") ON DELETE CASCADE
)""",
]

LEN_QUERIES = len(QUERIES)

WHERE_MAPPING = {
    "artist": '"Artists"."artist_name"',
    "character": '"Characters"."character_name"',
    "group": '"Groups"."group_name"',
    "language": '"Languages"."language_name"',
    "series": '"Series"."series_name"',
    "tag": '"Tags"."tag_name"',
    "type": '"Types"."type_name"',
    "source": '"Sources"."source_name"',
}
