fm163 - cli downloader for music.163.com
========================================

This README describes v0.4.0.
The `master` branch is in development and undocumented.

Dependencies
------------

- Python 3.6
- [sortedcontainers](https://pypi.python.org/pypi/sortedcontainers)
- a slightly modified version of [MusicBoxApi](https://github.com/wzpan/MusicBoxApi/issues/5)
- [netease-cloud-music-dl][ncm]

[ncm]: https://github.com/codezjx/netease-cloud-music-dl

Install
-------

Assuming you have already installed python-3.6 and [ncm]:

```sh
pip install sortedcontainers
pip install git+https://github.com/weakish/MusicBoxApi.git@too-many-tracks
git clone https://github.com/weakish/fm163.git
cd fm163
python fm163.py --help
```

Usage
-----

Currently it only supports download playlist.

```sh
python fm163.py playlist_id
```

Downloaded mp3 files will be saved in the directory specified in [ncm]
configuration file.

[ncm]: https//github.cezjx/netease-cloud-music-dl

All download music ids and meta data will be saved in `~/.fm163`.

```
~/.fm163
    history # history file (binary)
    songs_id.json # human-readable format converted via `fm163 -j`
    meta.json # meta data of music, name, url, album, artist, etc
```

Already downloaded music (including different bit rates) will be skipped in future downloads.

`-D` means not downloading music files, but recording it in history (also records meta data).

Contributing
------------

Send pull requests at <https://github.com/weakish/fm163/>

Coding style I am using: <https://weakish.github.io/coding-style/python/>

License
-------

0BSD
