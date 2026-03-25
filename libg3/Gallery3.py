#
#    Author: Jay Deiman
#    Email: admin@splitstreams.com
#
#    This file is part of pylibgal3.
#
#    pylibgal3 is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    pylibgal3 is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with pylibgal3.  If not, see <http://www.gnu.org/licenses/>.
#

__all__ = ['Gallery3', 'G3Client', 'login']

from urllib.parse import quote, urlencode

import requests

from .Errors import G3RequestError, G3UnknownError
from .G3Items import getItemFromResp, getItemsFromResp, parseItem

try:
    import json
except ImportError:
    try:
        import simplejson
    except ImportError:
        raise ImportError('You must have either the "json" or "simplejson"'
                          'library installed!')


class Gallery3(object):
    """Main utility class that should be instantiated and used for all calls."""

    def __init__(self, host, apiKey, g3Base='/gallery3', port=443):
        """
        Initialize the Gallery 3 object.

        @param host: The hostname of the gallery site
        @param apiKey: The api key to use for the connections
        @param g3Base: The remote url path to your gallery 3 install
        """
        protocol = 'https'
        self.base_url = f"{protocol}://{host}:{port}/{g3Base.strip('/')}"
        self.client = G3Client(self.base_url, apiKey)
        self.root = None

    def _url(self, resource, params=None):
        url = f"{self.base_url}/{quote(resource)}"
        if params:
            url += f"?{urlencode(params)}"
        return url

    def get(self, url):
        return self.client.request('GET', url)

    def post(self, url, data=None, headers=None):
        return self.client.request('POST', url, data=data, headers=headers)

    def put(self, url, data=None):
        return self.client.request('PUT', url, data=data)

    def delete(self, url):
        return self.client.request('DELETE', url)

    def getRoot(self):
        if not self.root:
            resp = self.get(self._url('index.php/rest/item/1'))
            self.root = parseItem(resp.json(), self)
        return self.root

    def getRandomImage(self, album, direct=True):
        """
        Get a random image for the album.

        @param album: The album object to pull the random image from
        @param direct: If set to False, the image may be pulled from a sub-album
        @return: a RemoteImage instance
        """
        scope = ('all', 'direct')[direct]
        data = {
            'type': 'photo',
            'random': 'true',
            'scope': scope,
        }
        url = '%s?%s' % (album.url, urlencode(data))
        resp = self.getRespFromUrl(url)
        return getItemFromResp(resp, self)

    def getRespFromUrl(self, url):
        """
        Get the response object given a full URL.

        @param url: the url to the resource (on the server)
        @return: object identified by the url
        """
        return self.get(url)

    def getRespFromUri(self, uri, kwargs={}):
        """
        Get the response object with the given URI.

        @param uri: The uri string defining the resource on the defined host
        @return: The 'addinfourl' response object
        """
        url = self._url(uri, kwargs)
        return self.getRespFromUrl(url)

    def getItemsForUrls(self, urls, parent=None):
        """
        Get an item for each specified URL.

        @param urls: list of urls to retrieve
        @return: a list of the corresponding remote objects
        """
        numUrls = len(urls)
        start = 0
        increment = 25
        ret = []
        while start < numUrls:
            data = {
                'urls': json.dumps(urls[start:start+increment]),
                'num': str(increment),
                'start': str(start),
            }
            resp = self.getRespFromUri('index.php/rest/items', data)
            # ret.extend(getItemsFromResp(resp, self, parent))
            items = getItemsFromResp(resp, self, parent)
            # FIXME work-around for empty items list
            if items is not None:
                ret.extend(items)
            start += increment
        return ret


class G3Client:

    def __init__(self, base_url, api_key=None):
        self.session = requests.Session()
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _headers(self, method):
        headers = {
            'X-Gallery-Request-Method': method.lower(),
        }
        if self.api_key:
            headers['X-Gallery-Request-Key'] = self.api_key
        return headers

    def request(self, method, url,
                data=None, headers=None, files=None):
        # unpack dictionary
        headers = {**self._headers(method), **(headers or {})}
        try:
            resp = self.session.request(
                method=method,
                url=url,
                headers=headers,
                data=data,
                files=files,
            )
            resp.raise_for_status()
            return resp
        except requests.HTTPError:
            try:
                err = resp.json()
                if 'errors' in err:
                    raise G3RequestError(err['errors'])
            except Exception:
                pass
            raise G3UnknownError(f"HTTP error: {resp.status_code}")

    def delete(self, url):
        resp = self.session.delete(url)
        resp.raise_for_status()
        return resp.status_code == 20


def login(host, username, passwd, g3Base='/gallery3', port=443):
    """
    Log you in.

    @param host: The hostname of the gallery site
    @param username: The username to login with
    @param passwd: The password to login with
    @param g3Base: The remote url path to your gallery 3 install
    @param port: The port number to connect to

    @return: a Gallery3 object on success, otherwise None
    """
    data = {
        'user': username,
        'password': passwd,
    }
    url = f'https://{host}:{port}/{g3Base}/index.php/rest'
    try:
        resp = requests.post(url, data=data)
        resp.raise_for_status()
    except requests.exceptions.RequestException as err:
        print(f"Login error: {err}")
        return None
    # apiKey = resp.text.strip('\'"')  # DEBUG
    # print(f"apiKey: {apiKey}")  # DEBUG
