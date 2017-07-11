#!/usr/bin/env python

import argparse
import json
import os
import pickle
import sys
import tempfile
import traceback
from pickle import PicklingError

from typing import Dict, Any, Union, List, Tuple, TextIO, Callable

from pickle import UnpicklingError
from sortedcontainers import SortedSet
from NetEaseMusicApi import api
from pathlib import Path


def configuration_directory() -> Path:
    return Path.home().joinpath('.fm163')


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


def json_dump(thing: Any, path: Path) -> None:
    """Fast dump to pretty formatted JSON file."""
    temporary_file_handler: int
    temporary_file_path: str
    temporary_file_handler, temporary_file_path = tempfile.mkstemp(dir=os.getcwd(), text=True)
    try:
        with open(temporary_file_path, 'w', newline='\n') as temporary_file:
            json.dump(thing, temporary_file,
                      check_circular=False, allow_nan=False,
                      indent=2, separators=(',', ': '))
    except (OverflowError, TypeError, ValueError):
        bug()
    else:
        os.close(temporary_file_handler)
        os.replace(temporary_file_path, path)


def marshal_dump(thing: Any, path: Path) -> None:
    temporary_file_handler: int
    temporary_file_path: str
    temporary_file_handler, temporary_file_path = tempfile.mkstemp(dir=os.getcwd(), text=True)
    try:
        with open(temporary_file_path, 'wb') as temporary_file:
            pickle.dump(thing, temporary_file)
    except PicklingError:
        bug()
    else:
        os.close(temporary_file_handler)
        os.replace(temporary_file_path, path)


def print_utf8(text: str) -> None:
    """Print UTF-8 text, working around with Windows."""
    sys.stdout.buffer.write(text.encode('utf-8'))


Track = Dict[str, Any]


def skip_download(track: Track) -> None:
    print_utf8(
        f"SKIP {track['name']} http://music.163.com/#/song?id={track['id']}\n"
    )


def cannot_download(track: Track) -> None:
    """Cannot find the download link on server."""
    print_utf8(
        f"UNAVAILABLE {track['name']} http://music.163.com/#/song?id={track['id']}\n"
    )

Meta = List[Track]


def load_meta() -> Meta:
    with open(meta_db(), 'r') as meta_file:
        try:
            return json.load(meta_file)
        except json.JSONDecodeError:
            bug()

# FIXME use a more concrete type
# `SortedSet[int]` does not work. (because no stubs?)
History = SortedSet


def load_history() -> History:
    with open(history_db(), 'rb') as history_file:
        try:
            return pickle.load(history_file)
        except UnpicklingError:
            bug()


def export_history() -> None:
    history: History = load_history()
    json_dump(list(history), configuration_file('songs_id.json'))


def save(record: Union[Meta, History]):
    # Parametrized generics cannot be used with class or instance checks.
    if isinstance(record, List):
        json_dump(record, meta_db())
    elif isinstance(record, SortedSet):
        marshal_dump(record, history_db())


def dfsId(track: Track, qualities: Tuple[str]):
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
                    dfs_id: int = track[quality]['dfsId']
                    if dfsId is None:
                        pass
                    else:
                        return dfs_id
    else:
        raise KeyError()


Playlist = Dict[str, Any]


def download_file(dfs_id: int):
    with open(f'{dfs_id}.mp3', 'wb') as f:
        f.write(api.download(dfs_id))


def download(list_id: int, dry_run: bool, hq: bool):
    history: History = load_history()
    meta: Meta = load_meta()

    if hq:
        qualities: Tuple[str] = ('hMusic', 'bMusic', 'mMusic', 'lMusic')
    else:
        qualities: Tuple[str] = ('mMusic', 'hMusic', 'bMusic', 'lMusic')

    playlist: Playlist = api.playlist.detail(list_id)

    for track in playlist["tracks"]:
        track_id: int = track["id"]
        if track_id in history:
            skip_download(track)
        else:
            if dry_run:
                pass
            else:
                try:
                    dfs_id: int = dfsId(track, qualities)
                except KeyError:
                    cannot_download(track)
                else:
                    download_file(dfs_id)

            meta.append(track)
            history.add(track_id)
            pass
        pass

    save(meta)
    save(history)


def catchEOFError() -> None:
    print(f"Error: file is empty.", file=sys.stderr)
    traceback.print_exc()
    sys.exit(getattr(os, 'EX_IOERR', 74))


def catchOSError(e: OSError) -> None:
    print(f"Error encountered to access file {e.filename}\n" +
          f"errno {e.errno}: {e.strerror}.",
          file=sys.stderr)
    traceback.print_exc()
    sys.exit(getattr(os, 'EX_IOERR', 74))


def catchError(e: Union[EOFError, OSError]) -> None:
    if isinstance(e, EOFError):
        catchEOFError()
    elif isinstance(e, OSError):
        catchOSError(e)


def playlist_id(string: str) -> int:
    try:
        result: int = int(string)
    except ValueError:  # assuming url
        from urllib.parse import urlparse, parse_qs

        # NetEase cloud music uses pseudo url queries.
        url_string: str = string.replace('/#', '')
        url_components = Tuple[str, str, str, str, str, str]
        url: url_components = urlparse(url_string)
        # [PY-4611](https://youtrack.jetbrains.com/issue/PY-4611)
        # is fixed in build 112.66, which is not released yet.
        #
        # noinspection PyUnresolvedReferences
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


def main():
    argumentParser = argparse.ArgumentParser(prog='fm163')
    argumentParser.add_argument('playlist_id', type=playlist_id, nargs='?', default=-1)
    mutuallyExclusiveGroup = argumentParser.add_mutually_exclusive_group()
    mutuallyExclusiveGroup.add_argument(
        '-D', action='store_true',
        help='dry run (record history and meta data, without downloading)')
    mutuallyExclusiveGroup.add_argument(
        '-H', action='store_true',
        help='prefer highest bit rate')
    mutuallyExclusiveGroup.add_argument(
        '-j', action='store_true',
        help='export history to json file')

    arguments = argumentParser.parse_args()
    if arguments.j:
        try:
            export_history()
        except (EOFError, OSError) as e:
            catchError(e)
    else:
        if arguments.playlist_id >= 0:
            try:
                download(arguments.playlist_id, arguments.D, arguments.H)
            except (EOFError, OSError) as e:
                catchError(e)
        else:
            usage()
            sys.exit(getattr(os, 'EX_USAGE', 64))


if __name__ == "__main__":
    main()
