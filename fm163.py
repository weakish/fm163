#!/usr/bin/env python

import argparse
import http.client
import json
import os
import pickle
import subprocess
import sys
import traceback
from pathlib import Path
from pickle import UnpicklingError
from typing import Dict, Any, Union, List, Tuple, TextIO, Callable

import leancloud
from MusicBoxApi import api
from MusicBoxApi.api import NetEase
from MusicBoxApi.api import TooManyTracksException
from sortedcontainers import SortedSet


def configuration_directory() -> Path:
    configuration_path: Path = Path.home().joinpath('.fm163')
    if configuration_path.exists():
        return configuration_path
    else:
        try:
            configuration_path.mkdir(parents=True)
            return configuration_path
        except FileExistsError:
            print(
                '''fm163 uses `~/.fm163` as the data directory.
                but a file named `~/.fm163` already exist.
                Abort now. Please rename or move `~/.fm163`.
                ''',
                file=sys.stderr)
            ex_config = 78
            sys.exit(ex_config)


def configuration_file(name: str) -> Path:
    return configuration_directory().joinpath(name)


def meta_db() -> Path:
    return configuration_file('meta.json')


def history_db() -> Path:
    return configuration_file('history')


def usage() -> None:
    print('Usage: fm163 PLAYLIST_ID')


def bug() -> None:
    """Print instructions on how to report a bug."""
    print('Most likely you have encountered a bug.\n' +
          'Please report it at https://github.com/weakish/fm163\n' +
          'Thanks.\n' + '\n' +
          'Stacktrace:\n',
          file=sys.stderr)
    traceback.print_exc()
    sys.exit(getattr(os, 'EX_SOFTWARE', 70))


Serializer = Callable[[Any, TextIO], None]


def serialize_with_json(thing: Any, file: TextIO) -> None:
    """Fast dump to pretty formatted JSON file."""
    json.dump(thing, file,
              check_circular=False, allow_nan=False,
              indent=2, separators=(',', ': '))


def print_utf8(text: str) -> None:
    """Print UTF-8 text, working around with Windows."""
    sys.stdout.buffer.write(text.encode('utf-8'))


Track = Dict[str, Any]


def skip(track: Track, msg: str = "SKIP") -> None:
    print_utf8(
        f"{msg} {track['name']} http://music.163.com/#/song?id={track['id']}\n"
    )


def load_history() -> SortedSet:
    try:
        history_file = history_db().open(mode="rb")
        try:
            return pickle.load(history_file)
        except UnpicklingError:
            bug()
        finally:
            history_file.close()

    except FileNotFoundError:
        return SortedSet([])


def dfs_id(track: Track, qualities: Tuple[str, ...]) -> int:
    """
    Returns dfsId of Track, with priority given in qualities.

    Raises KeyError() when dfsId not found.
    """
    for quality in qualities:
        if quality in track:
            if track[quality] is None:
                pass
            else:
                if 'dfsId' in track[quality]:
                    dfsid: int = track[quality]['dfsId']
                    if dfsid is None:
                        pass
                    else:
                        return dfsid
    else:
        raise KeyError()


def load_keys() -> Tuple[str, str]:
    app_id: str = os.environ['LEANCLOUD_APP_ID']
    app_key: str = os.environ['LEANCLOUD_APP_KEY']
    return app_id, app_key


Playlist = List[Dict[str, Any]]


# TODO Also download lyrics https://github.com/littlecodersh/NetEaseMusicApi/pull/2
def prepare_download(list_id: int) -> Tuple[List[Track], List[Track]]:
    """Raises:
        TooManyTracksException: when the playlist is longer than 1000."""

    app_id: str
    app_key: str
    app_id, app_key = load_keys()
    leancloud.init(app_id, app_key)

    netease: NetEase = api.NetEase()
    playlist: Playlist = netease.playlist_detail(list_id)

    lean_track = leancloud.Object.extend('Track')
    query = lean_track.query

    skipped: List[Track] = []
    to_download: List[Track] = []
    for track in playlist:
        track_id: str = str(track["id"])
        query.equal_to('objectId', track_id)
        if query.count() == 0:
            to_download.append(track)
        else:
            skipped.append(track)

    return skipped, to_download


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


def save_meta_info(tracks: List[Track]):
    subdomain: str = os.environ['LEANCLOUD_APP_ID'][0:8].lower()
    conn = http.client.HTTPSConnection(f"{subdomain}.api.lncldglobal.com")
    app_id: str
    app_key: str
    app_id, app_key = load_keys()
    headers = {
        'x-lc-id': app_id,
        'x-lc-key': app_key,
        'content-type': "application/json"
    }
    for track in tracks:
        track["objectId"] = str(track["id"])
        conn.request("POST", "/1.1/classes/Track", json.dumps(track), headers)
        response = conn.getresponse()
        if response.status == 201:
            response.read()
        else:
            skip(track, "Failed to save meta info for")
            print(response.status, response.reason)
            print(response.read())
    conn.close()


def main():
    argument_parser = argparse.ArgumentParser(prog='fm163')
    argument_parser.add_argument('playlist_id', type=playlist_id, nargs='?', default=-1)
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group()
    mutually_exclusive_group.add_argument(
        '-D', action='store_true',
        help='dry run (record history and meta data, without downloading)')

    arguments = argument_parser.parse_args()
    if arguments.playlist_id >= 0:
        try:
            skipped: List[Track]
            to_download: List[Track]
            skipped, to_download = prepare_download(arguments.playlist_id)
        except TooManyTracksException as e:
            sys.stderr.write(e)
            sys.exit(1)
        except (EOFError, OSError) as e:
            catch_error(e)
        else:
            if len(to_download) == 0:
                print("\nSkipped all tracks in the playlist.")
                sys.exit(0)
            else:
                print(f"\nSkipped {len(skipped)} tracks in the playlist.")
                for track in skipped:
                    skip(track)
                save_meta_info(to_download)

    else:
        usage()
        sys.exit(getattr(os, 'EX_USAGE', 64))


if __name__ == "__main__":
    main()
