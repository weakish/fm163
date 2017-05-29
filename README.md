fm163 - cli downloader for music.163.com
========================================

Dependencies
------------

- Python 3.6
- [sortedcontainers](https://pypi.python.org/pypi/sortedcontainers)
- [NetEaseMusicApi](https://github.com/littlecodersh/NetEaseMusicApi)

Install
-------

```sh
pip install sortedcontainers
pip install NetEaseMusicApi
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

Downloaded mp3 files will be saved in current directory.

All download music ids and meta data will be saved in `~/.fm163`.

```
~/.fm163
    history # history file (binary)
    songs_id.json # human-readable format converted via `fm163 -j`
    meta.json # meta data of music, name, url, album, artist, etc
```

Already downloaded music (including different bit rates) will be skipped in future downloads.

By default it will download the 160 kbps version.
If it is not available, it will fall back to download 320 kbps.
If 320 kbps is also available, it will try to download the 96 kbps version.

Adding `-H` option will download the highest bit rates version available.

`-D` means not downloading music files, but records it in history (also records meta data).

Contributing
------------

Send pull requests at <https://github.com/weakish/fm163/>

Coding style I am using: <https://weakish.github.io/coding-style/python/>

License
-------

0BSD
