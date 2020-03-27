#!/usr/bin/env python3.8

import argparse
import http.client
import json
import os
import subprocess
import sys
from typing import Callable, Dict, Any, List, Tuple, Final, Iterable
from urllib.parse import urlparse, parse_qs

import leancloud
from MusicBoxApi import api
from MusicBoxApi.api import TooManyTracksException
from pypinyin import lazy_pinyin

from nonpythonic import fn, for_each, catch

Track = Dict[str, Any]
Playlist = List[Dict[str, Any]]

# Windows workaround
print_utf8: Final[Callable[[str], None]] = lambda text, /: fn(sys.stdout.buffer.write(text.encode('utf-8')))
skip: Final[Callable[[str, int, str], None]] = lambda track_name, track_id, msg = "SKIP", /: print_utf8(
    f"{msg} {track_name} http://music.163.com/#/song?id={track_id}\n")
load_keys: Final[Callable[[], Tuple[str, str]]] = lambda: (
    os.environ['LEANCLOUD_APP_ID'],
    os.environ['LEANCLOUD_APP_KEY'])
prepare_download: Final[Callable[[Playlist], Tuple[List[Tuple[str, int]], List[str]]]] = lambda playlist, /: fn(
    leancloud.init(*load_keys()),
    track_id_list := [str(track["id"]) for track in playlist],
    query := leancloud.Object.extend('Track').query.contained_in('objectId', track_id_list).limit(1000).select("name"),
    ret=(sorted(
        [(track.get("name"), int(track.id)) for track in query.find()],
        key=lambda t: lazy_pinyin(t[0])[0].lower()), track_id_list))
download_track: Final[Callable[[int, bool], None]] = lambda track_id, dry_run: not dry_run and fn(
    subprocess.run(["ncm", "-s", str(track_id)]))
parse_playlist_url: Final[Callable[[str], int]] = lambda string, /: fn(
    # NetEase cloud music uses pseudo url queries.
    url_string := string.replace('/#', ''),
    url := urlparse(url_string),
    queries := parse_qs(url.query),
    ret=int(queries['id'][0]))
playlist_id: Final[Callable[[str], int]] = lambda string, /: parse_playlist_url(string) if "/#" in string else int(string)
save_meta_info: Final[Callable[[Iterable[Track]], None]] = lambda tracks, /: fn(
    subdomain := os.environ['LEANCLOUD_APP_ID'][0:8].lower(),
    conn := http.client.HTTPSConnection(f"{subdomain}.api.lncldglobal.com"),
    headers := {
        'x-lc-id': load_keys()[0],
        'x-lc-key': load_keys()[1],
        'content-type': "application/json"
    },
    for_each(tracks, lambda track: fn(
        track.setdefault("objectId", str(track["id"])),
        conn.request("POST", "/1.1/classes/Track", json.dumps(track), headers),
        response := conn.getresponse(),
        response.read() if response.status == 201 else fn(
            skip(track['name'], track['id'], "Failed to save meta info for"),
            print(response.status, response.reason),
            print(response.read())))),
    conn.close())

main: Final[Callable[[], None]] = lambda: fn(
    argument_parser := argparse.ArgumentParser(prog='fm163'),
    argument_parser.add_argument('playlist_id', type=playlist_id, nargs='?', default=-1),
    mutually_exclusive_group := argument_parser.add_mutually_exclusive_group(),
    mutually_exclusive_group.add_argument(
        '-D', action='store_true',
        help='dry run (record history and meta data, without downloading)'),
    arguments := argument_parser.parse_args(),
    catch(
        lambda: fn(
            netease := api.NetEase(),
            playlist := netease.playlist_detail(arguments.playlist_id),
            ret=prepare_download(playlist) + (playlist,)),
        {
            TooManyTracksException: lambda e: fn(
                sys.stderr.write(str(e)),
                sys.exit(1)),
        },
        lambda values: fn(
            skipped := values[0],
            track_id_list := values[1],
            playlist := values[2],
            ret=fn(
                print("\nSkipped all tracks in the playlist."),
                sys.exit(0)) if len(skipped) == len(track_id_list) else fn(
                print(f"\nSkipped {len(skipped)} tracks in the playlist."),
                for_each(skipped, lambda skipped_track: skip(skipped_track[0], skipped_track[1])),
                skipped_id := {elem[1] for elem in skipped},
                to_download_id := {int(track_id) for track_id in track_id_list} - skipped_id,
                to_download := filter(lambda track: track["id"] in to_download_id, playlist),
                save_meta_info(to_download))) if arguments.playlist_id >= 0 else fn(
                    print("Run `fm163 -h` for help info."),
                    sys.exit(getattr(os, 'EX_USAGE', 64)))))
__name__ == "__main__" and main()
