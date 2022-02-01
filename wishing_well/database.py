import logging
import json
from json.decoder import JSONDecodeError
from shutil import copyfile
import sqlite3


from .util import get_data_path, show_error
from .enums import ItemType


DATABASE_VERSION = 1


# decode item types stored in json.
# this is still required for migrating json data to sqlite
def decode_item_type(dict_):
    if '__enum__' in dict_:
        return getattr(ItemType, dict_['__enum__'])
    return dict_

# convert a bytestring stored in sqlite back to our enum
def convert_reward_type(b):
    return ItemType(int(b))


# register converter for the item type enum
sqlite3.register_converter('ITEM_TYPE', convert_reward_type)


class DatabaseConnectionContextManager:
    def __init__(self, database_path):
        self._database_path = database_path
        self._connection = sqlite3.connect(self._database_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self._connection.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.cursor.close()
        self._connection.close()

        # to not ignore any exceptions that happened inside a with block
        return False

    def commit(self):
        self._connection.commit()

class Database:
    def __init__(self):
        data_path = get_data_path()
        self._database_path = data_path / 'database.sqlite3'

        # create the database if it does not exist yet
        if not self._database_path.exists():
            self._create_database()
        elif self._database_path.is_dir():
            show_error(f'{self._database_path} exists, but is not a file.')

        # the database exists, let's check the version of our data
        logging.info('Checking database version')
        with self._get_database_connection() as db:
            try:
                version = db.cursor.execute('SELECT data FROM meta WHERE name = "version"').fetchall()[0][0]
            except (IndexError, sqlite3.DatabaseError, sqlite3.OperationalError):
                show_error('Could not find version information in the database. The database might be corrupt.')

        # exit if the version does not match. in the future, migrate if version is lower
        if version != DATABASE_VERSION:
            show_error('Unknown database version. Shutting down to not mess with any data.')

        # create a backup
        logging.info('Creating database backup')
        copyfile(self._database_path, data_path / 'database.sqlite3.bak')

    def _get_database_connection(self):
        return DatabaseConnectionContextManager(self._database_path)

    def _create_database(self):
        logging.info('No existing database found, creating new one')

        with self._get_database_connection() as db:
            # create tables
            db.cursor.execute('CREATE TABLE meta (name TEXT PRIMARY KEY, data BLOB)')
            db.cursor.execute('CREATE TABLE banner_types (id INTEGER PRIMARY KEY, name TEXT)')
            db.cursor.execute('''
                CREATE TABLE wish_history (
                    id INTEGER,
                    uid INTEGER,
                    banner_type INTEGER,
                    type ITEM_TYPE,
                    rarity INTEGER,
                    time TEXT,
                    name TEXT,
                    UNIQUE (id, uid)
                )
            ''')

            # insert version
            db.cursor.execute('INSERT INTO meta VALUES ("version", ?)', (DATABASE_VERSION,))
            db.commit()

            # check if there's an old .json database we can convert
            data_path = get_data_path()
            json_database_path = data_path / 'database.json'
            if json_database_path.exists():
                logging.info('Found old database.json, converting to new format')
                old_data = None
                with json_database_path.open('r', encoding='utf-8') as fp:
                    try:
                        old_data = json.load(fp, object_hook=decode_item_type)
                    except JSONDecodeError:
                        show_error(f'Fould old data at {json_database_path}, but could not read it. Aborting.')

                # we have old data, let's insert it into our new sqlite db
                if old_data is not None:
                    if 'banner_types' in old_data:
                        for [ id_, name ] in old_data['banner_types'].items():
                            db.cursor.execute('INSERT INTO banner_types VALUES (?, ?)', (int(id_), name))

                    if 'wish_history' in old_data:
                        for uid in old_data['wish_history']:
                            for banner_type_id in old_data['wish_history'][uid]:
                                for wish in old_data['wish_history'][uid][banner_type_id]:
                                    db.cursor.execute('INSERT INTO wish_history VALUES (?, ?, ?, ?, ?, ?, ?)', (
                                        wish['id'],
                                        int(uid),
                                        int(banner_type_id),
                                        wish['type'],
                                        wish['rarity'],
                                        wish['time'],
                                        wish['name']
                                    ))

                db.commit()
                logging.info('Finished conversion, deleting old database.json')
                json_database_path.unlink()

    def get_banner_types(self):
        banner_types = {}
        with self._get_database_connection() as db:
            banner_types_tuples = db.cursor.execute('SELECT id, name FROM banner_types').fetchall()

        for banner_type in banner_types_tuples:
            banner_types[banner_type[0]] = banner_type[1]

        return banner_types

    def store_banner_types(self, banner_types):
        logging.info('Storing banner types')
        with self._get_database_connection() as db:
            db.cursor.executemany('''
                INSERT OR IGNORE INTO banner_types (id, name) VALUES (:key, :name)
            ''', banner_types)
            db.commit()

    def get_uids(self):
        with self._get_database_connection() as db:
            uids = db.cursor.execute('SELECT DISTINCT uid FROM wish_history').fetchall()

        for uid in uids:
            yield uid[0]

    def get_wish_history(self, uid):
        with self._get_database_connection() as db:
            wish_history = db.cursor.execute('''
                SELECT
                    id,
                    banner_type,
                    type,
                    rarity,
                    time,
                    name
                FROM wish_history WHERE uid = ? ORDER BY time ASC
            ''', (uid,)).fetchall()

        for wish in wish_history:
            yield {
                'id': wish[0],
                'banner_type': wish[1],
                'type': wish[2],
                'rarity': wish[3],
                'time': wish[4],
                'name': wish[5]
            }

    def get_latest_wish_id(self, uid, banner_type):
        with self._get_database_connection() as db:
            try:
                id_ = db.cursor.execute('SELECT MAX(id) FROM wish_history WHERE uid = ? AND banner_type = ?', (uid, banner_type)).fetchone()[0]
            except IndexError:
                id_ = None

        return id_

    def store_wish_history(self, wishes):
        if len(wishes) == 0:
            return

        logging.info('Storing wish history')
        with self._get_database_connection() as db:
            db.cursor.executemany('''
                INSERT OR IGNORE INTO wish_history
                ( id, uid, banner_type, type, rarity, time, name )
                VALUES
                ( :id, :uid, :banner_type, :type, :rarity, :time, :name )
            ''', wishes)
            db.commit()
