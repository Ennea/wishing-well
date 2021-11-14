import logging
import json
from json.decoder import JSONDecodeError


from .util import get_data_path, show_error
from .enums import ItemType
from .exceptions import UIDNotFoundError, NoWishHistoryError


def serialize_item_type(obj):
    if isinstance(obj, ItemType):
        return { '__enum__': str(obj).split('.')[1] }
    raise TypeError

def decode_item_type(dict_):
    if '__enum__' in dict_:
        return getattr(ItemType, dict_['__enum__'])
    return dict_


class Database:
    def __init__(self):
        data_path = get_data_path()
        self._database_path = data_path / 'database.json'
        logging.info('Loading database')
        try:
            with self._database_path.open('r', encoding='utf-8') as fp:
                try:
                    self._data = json.load(fp, object_hook=decode_item_type)
                    # write a backup
                    logging.info('Done loading, creating backup')
                    with (data_path / 'database.json.bak').open('w', encoding='utf-8') as fp_backup:
                        json.dump(self._data, fp_backup, default=serialize_item_type)
                except JSONDecodeError:
                    show_error(f'Could not parse {self._database_path} as valid JSON.')
        except FileNotFoundError:
            logging.info('No existing database found, creating new one')
            self._data = {
                'banner_types': {},
                'wish_history': {}
            }
            self._write_database()

    def _write_database(self):
        logging.info('Writing database to file system')
        with self._database_path.open('w', encoding='utf-8') as fp:
            json.dump(self._data, fp, default=serialize_item_type)

    def get_banner_types(self):
        try:
            return self._data['banner_types']
        except KeyError:
            return {}

    def store_banner_types(self, banner_types):
        logging.info('Storing banner types')
        self._data['banner_types'] = banner_types
        self._write_database()

    def get_uids(self):
        for uid in self._data['wish_history'].keys():
            yield uid

    def get_banner_types_for_uid(self, uid):
        try:
            for banner_type in self._data['wish_history'][uid].keys():
                yield banner_type
        except KeyError:
            raise UIDNotFoundError(f'No data for UID {uid}.')

    def get_wish_history(self, uid, banner_type):
        try:
            user = self._data['wish_history'][uid]
        except KeyError:
            raise UIDNotFoundError(f'No data for UID {uid}.')

        try:
            return user[banner_type]
        except KeyError:
            raise NoWishHistoryError(f'No data for banner type {banner_type}.')

    def get_latest_wish(self, uid, banner_type):
        try:
            return self.get_wish_history(uid, banner_type)[-1]
        except (UIDNotFoundError, NoWishHistoryError, IndexError):
            return None

    def store_wish_history(self, uid, banner_type, wishes):
        logging.info('Storing wish history')
        if uid is None or banner_type is None or len(wishes) == 0:
            return

        if uid not in self._data['wish_history']:
            self._data['wish_history'][uid] = {}

        if banner_type not in self._data['wish_history'][uid]:
            self._data['wish_history'][uid][banner_type] = []

        self._data['wish_history'][uid][banner_type] += wishes
        self._write_database()
