import json
import os
from copy import deepcopy
from typing import Any, Mapping, Union
from weakref import proxy

from library_of_h.constants import (USER_DATA_DIRECTORY,
                                    USER_PREFERENCES_LOCATION)
from library_of_h.miscellaneous.classes.nested_dict import NestedDict


class Preferences:

    _instance = None

    slots = "_preferences"
    _preferences_defaults = NestedDict(
        {
            "database_preferences": {
                "location": USER_DATA_DIRECTORY,
                "compare_like": False,
            },
            "download_preferences": {
                "overwrite": False,
                "destination_formats": {
                    "Hitomi": {
                        "Artist(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Character(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Gallery ID(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Group(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Series(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Type(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Tag(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                    },
                    "nhentai": {
                        "Artist(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Character(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Gallery ID(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Group(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Parody(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                        "Tag(s)": {
                            "location_format": USER_DATA_DIRECTORY
                            + "/{item}/{gallery_id}/",
                            "filename_format": "{filename}.{ext}",
                        },
                    },
                },
            },
        }
    )

    def __init__(self):
        raise RuntimeError(
            "Don't instantiate using Preferences(...), "
            "use Preferences.get_instance(...)"
        )

    def __eq__(self, other: Mapping):
        return self._preferences == other._preferences

    def __getitem__(self, key: Union[tuple[str, ...], str]):
        if key[0] == "default":
            return self._preferences_defaults[key[1:]]
        else:
            return self._preferences[key]

    def __setitem__(self, key: Union[tuple[str, ...], str], value: Any):
        self._preferences[key] = value

    def copy(self):
        return deepcopy(self)

    @classmethod
    def get_instance(cls) -> "Preferences":
        if cls._instance is None:
            self = cls.__new__(cls)
            # By default, _preferences is the same as _preferences_default, unless preferences.json
            # specifies otherswise.
            self._preferences = NestedDict(self._preferences_defaults)
            try:
                filename = USER_PREFERENCES_LOCATION
                if not os.path.getsize(filename):
                    raise ValueError("Empty file.")

                with open(filename) as file:
                    user_changes_dict = json.load(file)
            except (
                ValueError,  # preference.json is empty.
                FileNotFoundError,  # preference.json does not exist.
                json.JSONDecodeError,  # preference.json is malformed.
            ):
                self._preferences = NestedDict(self._preferences_defaults)
            else:
                self._preferences.nested_replace(user_changes_dict)
            cls._instance = self

        return cls._instance

    def nested_update(self, mapping: Mapping):
        self._preferences.nested_update(mapping)

    def nested_replace(self, mapping: Mapping):
        self._preferences.nested_replace(mapping)

    def save(self):
        with open(USER_PREFERENCES_LOCATION, "w") as preferences_file:
            json.dump(self._preferences.to_json(), preferences_file, indent=4)
        Preferences._instance = None


PREFERENCES_TEMPLATE = {
    "database_preferences": {"location": "", "compare_like": ""},
    "download_preferences": {
        "overwrite": "",
        "destination_formats": {
            "Hitomi": {
                "Artist(s)": {"location_format": "", "filename_format": ""},
                "Character(s)": {"location_format": "", "filename_format": ""},
                "Gallery ID(s)": {"location_format": "", "filename_format": ""},
                "Group(s)": {"location_format": "", "filename_format": ""},
                "Series(s)": {"location_format": "", "filename_format": ""},
                "Type(s)": {"location_format": "", "filename_format": ""},
                "Tag(s)": {"location_format": "", "filename_format": ""},
            },
            "nhentai": {
                "Artist(s)": {"location_format": "", "filename_format": ""},
                "Character(s)": {"location_format": "", "filename_format": ""},
                "Gallery ID(s)": {"location_format": "", "filename_format": ""},
                "Group(s)": {"location_format": "", "filename_format": ""},
                "Parody(s)": {"location_format": "", "filename_format": ""},
                "Tag(s)": {"location_format": "", "filename_format": ""},
            },
        },
    },
}
