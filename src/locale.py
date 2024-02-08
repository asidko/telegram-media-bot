import os
from os.path import dirname, realpath

import yaml

current_dir_path = dirname(realpath(__file__))
yaml_path = os.path.join(current_dir_path, '..', 'locale.yaml')

def load_locales(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

locales = load_locales(yaml_path)

def localized(message, string_key, *args):
    default_lang = 'en'
    user_lang = message.from_user.language_code if message.from_user.language_code in locales else default_lang
    localized_string = locales.get(user_lang, {}).get(string_key, string_key)
    return localized_string.format(*args)
