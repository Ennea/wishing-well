import logging
import sys
import webbrowser
from copy import deepcopy
from pathlib import Path
from threading import Timer
from time import time

from .client import Client
from .enums import ItemType
from .exceptions import AuthTokenExtractionError, MissingAuthTokenError, EndpointError, RequestError


class Server:
    _heartbeat_timeout = 90  # seconds to shutdown after receiving no heartbeat
    _static_headers = { 'Cache-Control': 'no-store' }

    def __init__(self, bottle, port):
        self._bottle = bottle
        self._client = Client()
        self._app = self._bottle.Bottle()

        self._app.route('/', callback=self._index)
        self._app.route('/static/<filename>', callback=self._static_files)
        self._app.route('/wishing-well', callback=self._identify)
        self._app.route('/data', callback=self._get_data)
        self._app.route('/update-wish-history', method='POST', callback=self._update_wish_history)
        self._app.route('/heartbeat', method='POST', callback=self._heartbeat)

        self._server = self._bottle.WSGIRefServer(host='localhost', port=port)
        self._last_heartbeat = time()
        self._shutdown_timer = Timer(self._heartbeat_timeout, self._shutdown)
        self._shutdown_timer.start()

        webbrowser.open(f'http://localhost:{port}')
        self._bottle.run(self._app, server=self._server)

    def _shutdown(self):
        logging.debug('No longer receiving heartbeats. Shutting down.')
        self._server.srv.shutdown()

    def _index(self):
        return self._bottle.static_file('index.html', root=Path(sys.path[0]) / 'frontend', headers=self._static_headers)

    def _static_files(self, filename):
        return self._bottle.static_file(filename, root=Path(sys.path[0]) / 'frontend', headers=self._static_headers)

    # a simple 204 on a fixed endpoint name;
    # used to identify ourselves to check if there's already an
    # instance of wishing well running when we start it
    def _identify(self):
        self._bottle.response.status = 204

    # heartbeat. if this isn't called every X seconds, shut down
    def _heartbeat(self):
        time_ = time()
        logging.debug('Last heartbeat: %fs ago', time_ - self._last_heartbeat)
        self._last_heartbeat = time_
        self._shutdown_timer.cancel()
        self._shutdown_timer = Timer(self._heartbeat_timeout, self._shutdown)
        self._shutdown_timer.start()

    # return all data required by the frontend
    def _get_data(self):
        # banner types
        banner_types = self._client.get_banner_types()

        # pity template
        pity_template = {}
        for key, name in banner_types.items():
            pity_template[key] = {
                'name': name,
                'pity4': 0,
                'pity5': 0
            }

        uids = {}
        for uid in self._client.get_uids():
            uids[uid] = {
                'statistics': {
                    'characters5': { 'total': 0, 'averagePity': [] },
                    'weapons5': { 'total': 0, 'averagePity': [] },
                    'characters4': { 'total': 0, 'averagePity': [] },
                    'weapons4': { 'total': 0, 'averagePity': [] },
                    'weapons3': { 'total': 0 }
                },
                'pity': deepcopy(pity_template),
                'lowPity': [],
                'wishHistory': []
            }

            # shorthands
            data = uids[uid]
            stats = data['statistics']
            pity = data['pity']
            low_pity = data['lowPity']
            wish_history = data['wishHistory']

            for banner_type in self._client.get_banner_types_for_uid(uid):
                for wish in self._client.get_wish_history(uid, banner_type):
                    # stat and pity calculation
                    # 5 star
                    if wish['rarity'] == 5:
                        if wish['type'] is ItemType.CHARACTER:
                            stats['characters5']['total'] += 1
                            stats['characters5']['averagePity'].append(pity[banner_type]['pity5'] + 1)
                        else:
                            stats['weapons5']['total'] += 1
                            stats['weapons5']['averagePity'].append(pity[banner_type]['pity5'] + 1)

                        low_pity.append({
                            'name': wish['name'],
                            'pity': pity[banner_type]['pity5'] + 1
                        })
                        pity[banner_type]['pity5'] = 0
                    else:
                        pity[banner_type]['pity5'] += 1

                    # 4 star
                    if wish['rarity'] == 4:
                        if wish['type'] is ItemType.CHARACTER:
                            stats['characters4']['total'] += 1
                            stats['characters4']['averagePity'].append(pity[banner_type]['pity4'] + 1)
                        else:
                            stats['weapons4']['total'] += 1
                            stats['weapons4']['averagePity'].append(pity[banner_type]['pity4'] + 1)

                        pity[banner_type]['pity4'] = 0
                    else:
                        pity[banner_type]['pity4'] += 1

                    # 3 star
                    if wish['rarity'] == 3:
                        stats['weapons3']['total'] += 1

                    # insert wish copy into frontend-ready history
                    wish_copy = wish.copy()
                    wish_copy['type'] = 'Character' if wish_copy['type'] is ItemType.CHARACTER else 'Weapon'
                    wish_copy['bannerType'] = banner_type
                    wish_copy['bannerTypeName'] = banner_types[banner_type]
                    wish_copy['rarityText'] = '★' * wish_copy['rarity']
                    wish_history.append(wish_copy)

            # calculate average pity
            for _, category in stats.items():
                if 'averagePity' in category:
                    category['averagePity'] = (
                        sum(category['averagePity']) / len(category['averagePity'])
                        if len(category['averagePity']) > 0 else 0
                    )

            # transform pity into a list
            if '100' in pity:
                del pity['100']  # remove novice wishes
            pity = [ banner for _, banner in pity.items() ]

            # sort low pity
            low_pity.sort(key=lambda reward: reward['pity'])

            # re-sort the history now that all banner types are
            # merged, then reverse it for display in the frontend
            wish_history.sort(key=lambda wish: wish['id'])
            for wish in wish_history:
                del wish['id']
            wish_history.reverse()

            data['totalWishes'] = len(wish_history)
            # uid loop end

        return {
            'bannerTypes': banner_types,
            'uids': uids
        }

    def _update_wish_history(self):
        body = self._bottle.request.json
        try:
            region, auth_token = Client.extract_region_and_auth_token(body['url'])
        except AuthTokenExtractionError as e:
            self._bottle.response.status = 400
            return {
                'message': str(e)
            }

        self._client.set_region_and_auth_token(region, auth_token)
        try:
            self._client.fetch_and_store_banner_types()
            new_wishes_count = self._client.fetch_and_store_wish_history()
        except (MissingAuthTokenError, RequestError, EndpointError) as e:
            self._bottle.response.status = 500
            return {
                'message': str(e)
            }

        return {
            'message': f'Retrieved {new_wishes_count} new {"wish" if new_wishes_count == 1 else "wishes"}.'
        }
