#!/usr/bin/env python

import argparse
import http.client
import json
import os
import subprocess
import sys
import traceback
from typing import Dict, Any, Union, List, Tuple, Set, Iterator

import leancloud
from MusicBoxApi import api
from MusicBoxApi.api import NetEase
from MusicBoxApi.api import TooManyTracksException
from pypinyin import lazy_pinyin


Track = Dict[str, Any]
Playlist = List[Dict[str, Any]]


def print_utf8(text: str) -> None:
    """Print UTF-8 text, working around with Windows."""
    sys.stdout.buffer.write(text.encode('utf-8'))


def skip(track_name: str, track_id: int, msg: str = "SKIP") -> None:
    print_utf8(
        f"{msg} {track_name} http://music.163.com/#/song?id={track_id}\n"
    )


def load_keys() -> Tuple[str, str]:
    return os.environ['LEANCLOUD_APP_ID'], os.environ['LEANCLOUD_APP_KEY']


def prepare_download(playlist: Playlist) -> Tuple[List[Tuple[str, int]], List[str]]:
    """Raises:
        TooManyTracksException: when the playlist is longer than 1000."""

    app_id: str
    app_key: str
    app_id, app_key = load_keys()
    leancloud.init(app_id, app_key)

    track_id_list: List[str] = [str(track["id"]) for track in playlist]
    query: leancloud.Query = leancloud.Object.extend(
        'Track').query.contained_in('objectId', track_id_list).limit(1000).select("name")
    return (sorted([(track.get("name"), int(track.id)) for track in query.find()], key=lambda t: lazy_pinyin(t[0])[0].lower()),
            track_id_list)


def download_track(track_id: int, dry_run: bool) -> None:
    if dry_run:
        pass
    else:
        subprocess.run(["ncm", "-s", str(track_id)])


def catch_eof_error() -> None:
    print(f"Error: file is empty.", file=sys.stderr)
    traceback.print_exc()
    sys.exit(getattr(os, 'EX_IOERR', 74))


def catch_os_error(e: OSError) -> None:
    print(f"Error encountered to access file {e.filename}\n" +
          f"errno {e.errno}: {e.strerror}.",
          file=sys.stderr)
    traceback.print_exc()
    sys.exit(getattr(os, 'EX_IOERR', 74))


def catch_error(e: Union[EOFError, OSError]) -> None:
    if isinstance(e, EOFError):
        catch_eof_error()
    elif isinstance(e, OSError):
        catch_os_error(e)


def playlist_id(string: str) -> int:
    try:
        result: int = int(string)
    except ValueError:  # assuming url
        from urllib.parse import urlparse, parse_qs

        # NetEase cloud music uses pseudo url queries.
        url_string: str = string.replace('/#', '')
        url_components = Tuple[str, str, str, str, str, str]
        url: url_components = urlparse(url_string)
        queries: Dict[str, List[str]] = parse_qs(url.query)

        try:
            values: List[str] = queries['id']
        except KeyError:
            print(f"Invalid url: '{string}' does not contains query key 'id'", file=sys.stderr)
            sys.exit(getattr(os, 'EX_USAGE', 64))
        else:
            value: str = values[0]
            try:
                result: int = int(value)
            except ValueError:
                print(f"Invalid url: '{string}' contains an empty or noninteger id", file=sys.stderr)
                sys.exit(getattr(os, 'EX_USAGE', 64))
            else:
                return result
    else:
        return result


def save_meta_info(tracks: Iterator[Track]):
    subdomain: str = os.environ['LEANCLOUD_APP_ID'][0:8].lower()
    conn: http.client.HTTPConnection = http.client.HTTPSConnection(f"{subdomain}.api.lncldglobal.com")
    app_id: str
    app_key: str
    app_id, app_key = load_keys()
    headers: Dict[str, str] = {
        'x-lc-id': app_id,
        'x-lc-key': app_key,
        'content-type': "application/json"
    }
    for track in tracks:
        track["objectId"] = str(track["id"])
        conn.request("POST", "/1.1/classes/Track", json.dumps(track), headers)
        response: http.client.HTTPResponse = conn.getresponse()
        if response.status == 201:
            response.read()
        else:
            skip(track['name'], track['id'], "Failed to save meta info for")
            print(response.status, response.reason)
            print(response.read())
    conn.close()


def main():
    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(prog='fm163')
    argument_parser.add_argument('playlist_id', type=playlist_id, nargs='?', default=-1);
    mutually_exclusive_group: Any = argument_parser.add_mutually_exclusive_group();
    mutually_exclusive_group.add_argument(
        '-D', action='store_true',
        help='dry run (record history and meta data, without downloading)');

    arguments: argparse.Namespace = argument_parser.parse_args()
    if arguments.playlist_id >= 0:
        try:
            netease: NetEase = api.NetEase()
            playlist: Playlist = netease.playlist_detail(arguments.playlist_id)
            skipped: List[Tuple[str, int]]
            track_id_list: List[str]
            skipped, track_id_list = prepare_download(playlist)
        except TooManyTracksException as e:
            sys.stderr.write(str(e))
            sys.exit(1)
        except (EOFError, OSError) as e:
            catch_error(e)
        else:
            if len(skipped) == len(track_id_list):
                print("\nSkipped all tracks in the playlist.")
                sys.exit(0)
            else:
                print(f"\nSkipped {len(skipped)} tracks in the playlist.")
                for track_name, track_id in skipped:
                    skip(track_name, track_id)
                skipped_id: Set[int] = {elem[1] for elem in skipped}
                to_download_id: Set[int] = {int(track_id) for track_id in track_id_list} - skipped_id
                to_download: Iterator[Track] = filter(lambda track: track["id"] in to_download_id, playlist)
                save_meta_info(to_download)
    else:
        print("Run `fm163 -h` for help info.")
        sys.exit(getattr(os, 'EX_USAGE', 64))


if __name__ == "__main__":
    main()
