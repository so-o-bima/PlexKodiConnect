#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Synced playlists are stored in our plex.db. Interact with it through this
module
"""
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import Playlist, PlaylistError
from ..plex_db import PlexDB
from ..kodi_db import kodiid_from_filename
from .. import path_ops, utils, variables as v
###############################################################################
LOG = getLogger('PLEX.playlists.db')

###############################################################################


def plex_playlist_ids():
    """
    Returns a list of all Plex ids of the playlists already in our DB
    """
    with PlexDB() as plexdb:
        return list(plexdb.playlist_ids())


def kodi_playlist_paths():
    """
    Returns a list of all Kodi playlist paths of the playlists already synced
    """
    with PlexDB() as plexdb:
        return list(plexdb.kodi_playlist_paths())


def update_playlist(playlist, delete=False):
    """
    Assumes that all sync operations are over. Takes playlist [Playlist]
    and creates/updates the corresponding Plex playlists table entry

    Pass delete=True to delete the playlist entry
    """
    with PlexDB() as plexdb:
        if delete:
            plexdb.delete_playlist(playlist)
        else:
            plexdb.add_playlist(playlist)


def get_playlist(path=None, kodi_hash=None, plex_id=None):
    """
    Returns the playlist as a Playlist for either the plex_id, path or
    kodi_hash. kodi_hash will be more reliable as it includes path and file
    content.
    """
    playlist = Playlist()
    with PlexDB() as plexdb:
        playlist = plexdb.playlist(playlist, plex_id, path, kodi_hash)
    return playlist


def _m3u_iterator(text):
    """
    Yields e.g.
    http://127.0.0.1:<port>/plex/kodi/movies/file.strm?plex_id=...
    """
    lines = iter(text.split('\n'))
    for line in lines:
        if line.startswith('#EXTINF:'):
            yield next(lines).strip()


def m3u_to_plex_ids(playlist):
    """
    Adapter to process *.m3u playlist files. Encoding is not uniform!
    """
    plex_ids = list()
    with open(path_ops.encode_path(playlist.kodi_path), 'rb') as f:
        text = f.read()
    try:
        text = text.decode(v.M3U_ENCODING)
    except UnicodeDecodeError:
        LOG.warning('Fallback to ISO-8859-1 decoding for %s', playlist)
        text = text.decode('ISO-8859-1')
    for entry in _m3u_iterator(text):
        plex_id = utils.REGEX_PLEX_ID.search(entry)
        if plex_id:
            plex_id = plex_id.group(1)
            plex_ids.append(plex_id)
        else:
            # Add-on paths not working, try direct
            kodi_id, kodi_type = kodiid_from_filename(entry,
                                                      db_type=playlist.kodi_type)
            if not kodi_id:
                continue
            with PlexDB() as plexdb:
                item = plexdb.item_by_kodi_id(kodi_id, kodi_type)
            if item:
                plex_ids.append(item['plex_id'])
    return plex_ids


def playlist_file_to_plex_ids(playlist):
    """
    Takes the playlist file located at path [unicode] and parses it.
    Returns a list of plex_ids (str) or raises PL.PlaylistError if a single
    item cannot be parsed from Kodi to Plex.
    """
    if playlist.kodi_extension == 'm3u':
        plex_ids = m3u_to_plex_ids(playlist)
    else:
        LOG.error('Unsupported playlist extension: %s',
                  playlist.kodi_extension)
        raise PlaylistError
    return plex_ids
