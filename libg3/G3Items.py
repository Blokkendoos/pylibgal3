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

__all__ = ['Album', 'Image', 'LocalImage', 'RemoteImage', 'LocalMovie',
           'RemoteMovie', 'getItemFromResp', 'getItemsFromResp']

import datetime as dt
import mimetypes
import os

from .Errors import G3Error, G3InvalidRespError, G3UnknownTypeError
try:
    import json
except ImportError:
    try:
        import simplejson
    except ImportError:
        raise ImportError('You must have either the "json" or "simplejson"'
                          'library installed!')


class BaseRemote:

    def __init__(self, data, gallery, parent=None):
        """Initialize.

        @param data dict
        @param gallery Gallery3 object
        @param parent the parent object
        """
        self._data = data
        self._entity = data.get('entity', {})
        self._members = data.get('members', {})
        self._gallery = gallery
        self._parent = parent
        for k, v in {**data, **self._entity}.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"<{self.__class__.__name__} {getattr(self, 'title', '')}>"

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = value

    @property
    def created_dt(self):
        return dt.fromtimestamp(int(self.created)) if hasattr(self, 'created') else None

    @property
    def updated_dt(self):
        return dt.fromtimestamp(int(self.updated)) if hasattr(self, 'updated') else None

    @property
    def members(self):
        return self.getMemberObjects()

    @members.setter
    def members(self, value):
        self._members = value

    def delete(self):
        return self._gallery.delete(self.url)

    def refresh(self):
        resp = self._gallery.get(self.url)
        return parseItem(resp.json(), self._gallery, self._parent)

    def getMemberObjects(self):
        member_objs = self._gallery.getItemsForUrls(self._members, self)
        return member_objs


class Album(BaseRemote):

    def _getByType(self, t):
        ret = []
        for m in self.members:
            if m.type == t:
                ret.append(m)
        return ret

    def addImage(self, image, title='', description='', name=''):
        """
        Add image.

        @param image LocalImage
        """
        print(f"addImage image: {type(image)}")  # DEBUG
        entity = {
            "name": name,
            "type": image.type,
            "title": title,
            "description": description,
        }
        files = {
            "entity": (None, json.dumps(entity), 'application/json'),
            "file": (image.path, open(image.path, 'rb')),
        }
        # TODO use gallery (not gallery.client)
        resp = self._gallery.client.request('POST', self.url, files=files)
        url = resp.json()['url']
        return parseItem(self._gallery.get(url).json(), self, self)

    def getAlbums(self):
        """
        Get a list of the sub-albums in this album.

        @returns A list of Album objects
        """
        return self._getByType('album')

    Albums = property(getAlbums)

    def getImages(self):
        """
        Get all the images in this album.

        @returns A list of all images
        """
        return self._getByType('photo')

    Images = property(getImages)

    def getMovies(self):
        """
        Get all the movies in this album.

        @returns A list of all movies
        """
        return self._getByType('movie')

    Movies = property(getMovies)

    def getRandomImage(self, direct=True):
        """
        Get a random RemoteImage for the album.

        @param direct If set to False, the image may be pulled from a sub-album
        @returns a RemoteImage instance
        """
        return self._gallery.getRandomImage(self, direct)


class Image(object):
    contentType = ''


class LocalImage(Image):

    def __init__(self, path, replaceSpaces=True):
        if not os.path.isfile(path):
            raise IOError('%s is not a file' % path)
        self.path = path
        self.replaceSpaces = replaceSpaces
        self.Filename = os.path.basename(self.path)
        self.fh = None
        self.type = 'photo'

    def setContentType(self, ctype=None):
        if ctype is not None:
            self.contentType = ctype
        self.contentType = mimetypes.guess_type(self.getFileContents())[0] or \
            'application/octet-stream'

    def getContentType(self):
        if not self.contentType:
            self.setContentType()
        return self.contentType

    ContentType = property(getContentType, setContentType)

    def setFilename(self, name):
        self.filename = name
        if self.replaceSpaces:
            self.filename = self.filename.replace(' ', '_')

    def getFilename(self):
        return self.filename

    Filename = property(getFilename, setFilename)

    def getFileContents(self):
        """
        Get the entire contents of the file.

        @return File contents
        """
        if self.fh is None:
            self.fh = open(self.path, 'rb')
        self.fh.seek(0)
        return self.fh.read()

    def getUploadContent(self):
        """
        Get the upload content.

        @return the MIME headers and the actual
                binary content to be uploaded
        """
        ret = "Content-Disposition: form-data; name='file'; "
        ret += "filename='%s'\r\n" % self.filename
        ret += "Content-Type: %s\r\n" % self.ContentType
        ret += "Content-Transfer-Encoding: binary\r\n"
        ret += '\r\n'
        ret += self.getFileContents()
        ret += '\r\n'
        return ret

    def close(self):
        self.fh.close()


class RemoteImage(BaseRemote, Image):

    def addComment(self, comment):
        """
        Comment on this item.

        @param comment The comment
        @return The comment that was created
        """
        data = {
            'item': self.url,
            'text': comment,
        }
        url = self._gallery._url('comments')
        print(f"URL: {url}")
        print(f"DATA: {data}")
        resp = self._gallery.post(url, data=data)
        #resp = self._gallery.client.request('POST', self.url, files=files)

        ##print(f"URL: {self.url}")
        ##resp = self._gallery.post(self.url, data=data)

        #resp = self._gallery.post('comments', data=data)
        #url = resp.json()['url']
        #return parseItem(self._gallery.get(url).json(), self, self)

        ##img = getItemFromResp(resp, self._gallery)
        img = getItemFromResp(resp, self._gallery, self.parent)
        if hasattr(img, 'comments'):
            img.comments.append(comm)
        return comm

    def read(self, length=None):
        resp = self._gallery.getRespFromUrl(self.file_url)
        data = resp.content
        return data

    def getResized(self):
        """
        Get the "resized" version of the image.

        @return the resized image
        """
        img = None
        if hasattr(self, 'resize_url'):
            resp = self._gallery.getRespFromUrl(self.resize_url)
            img = resp.content
        return img

    def getThumbnail(self):
        """
        Get the "thumbnail" version of the image.

        @return the thumbnail image
        """
        img = None
        if hasattr(self, 'thumb_url'):
            resp = self._gallery.getRespFromUrl(self.thumb_url)
            img = resp.content
        return img


class LocalMovie(LocalImage):

    def __init__(self, path, replaceSpaces=True):
        LocalImage.__init__(self, path, replaceSpaces)
        self.type = 'movie'


class RemoteMovie(RemoteImage):
    pass


class Tag(BaseRemote):

    def __str__(self):
        return self.name

    def _postInit(self):
        if hasattr(self, 'count'):
            self.count = int(self.count)
        self.type = 'tag'

    def tag(self, tagName):
        raise G3Error('You cannot tag a Tag')


class Comment(BaseRemote):

    def __str__(self):
        return self.text

    def _postInit(self):
        # Change the "item" attribute to "parent" since that's what it is
        # I'm doing this to address overall consistency
        self._parent = None
        if hasattr(self, '_item'):
            self._parent = getattr(self, '_item')

    def tag(self, tagName):
        raise G3Error('You cannot tag a Comment')


def parseItem(data, gallery, parent=None):
    entity = data.get("entity", {})
    if "count" in entity:
        return Tag(data, gallery, parent)
    if "text" in entity:
        return Comment(data, gallery, parent)
    t = entity.get("type")
    if not t:
        raise G3InvalidRespError("Missing entity type")
    if t == "album":
        return Album(data, gallery, parent)
    elif t == "photo":
        return RemoteImage(data, gallery, parent)
    elif t == "movie":
        return RemoteMovie(data, gallery, parent)
    raise G3UnknownTypeError(f"Unknown type: {t}")


def getItemFromResp(response, gallery, parent=None):
    """
    Get the appropriate item for the given response object.

    @param response The (addinfourl) response object from the urllib2 request,
                    or a dict that has already been converted
    @param gallery The gallery object this is associated with
    @param parent The parent object for this item

    @returns a BaseRemote instance
    """
    gallery = gallery
    parent = parent

    if isinstance(response, dict):
        resp = response
    else:
        resp = json.loads(response.text)

    if 'count' in resp['entity']:
        # This is a tag, it doesn't have the same items as regular objects
        return Tag(resp, gallery, parent)
    if 'text' in resp['entity']:
        # This is a comment, it does not have the same items as regular objects
        return Comment(resp, gallery, parent)

    try:
        t = resp['entity']['type']
    except KeyError:
        raise G3InvalidRespError(f"Response contains no 'entity type': {response}")

    if t == 'album':
        return Album(resp, gallery, parent)
    elif t == 'photo':
        return RemoteImage(resp, gallery, parent)
    elif t == 'movie':
        return RemoteMovie(resp, gallery, parent)
    else:
        raise G3UnknownTypeError(f"Unknown entity type: '{t}'")


def getItemsFromResp(response, gallery, parent=None):
    """
    Get the corresponding items for the given list of items.

    @param response The (addinfourl) response object,
                    or a dict that has already been converted
    @param gallery The gallery object this is associated with
    @param parent The parent Album object for this item
    @returns a list of (BaseRemote) objects
    """
    ret = []
    lResp = json.loads(response.text)
    if not isinstance(lResp, list):
        lResp = list(response)
    for resp in lResp:
        ret.append(getItemFromResp(resp, gallery, parent))
    return ret
