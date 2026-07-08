from enum import StrEnum


class ProfileLang(StrEnum):
    EN_US = "en_US"
    EN_GB = "en_GB"
    FR_FR = "fr_FR"

    @classmethod
    def get_choices(cls):
        return [(choice.value, choice.name) for choice in cls]
