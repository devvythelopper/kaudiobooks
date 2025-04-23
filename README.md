```
usage: __main__.py [-h] {purge,download,convert,tag-to-name,name-to-tag,tag-to-dirname,dirname-to-tag,sanitize-dirnames,overwrite-title-from-track} ...

audiobooks manager. The directory structure used/applied by this software is `title -- author/title -- lpadded_track_num -- chapter title`. All problematic characters in title, author and chapter will be converted into lookalike characters from the
unicode character set when applied to the filename. All changes made are presented to the user beforehand and require manual commiting.

positional arguments:
  {purge,download,convert,tag-to-name,name-to-tag,tag-to-dirname,dirname-to-tag,sanitize-dirnames,overwrite-title-from-track}
    purge               purges .jpg and .m3u from audiobook directories. This gets rid of m3u and cover.jpg for example. Will only delete files from directories that actually contain audiobook files (mp3 files)
    download            downloads all audiobooks (that are not already present in the audible directory)
    convert             converts audiobooks from aac or aacx to mp3s using aaxtomp3 (this will not apply the directory structure used by kaudiobooks. You then manually check/change the id3 tags (with kid3 for example) and use kaudiobooks to apply
                        various mass operations.)
    tag-to-name         renames audiobook files from mp3 tags (only using tag version 2) replacing problematic characters with unicode lookalikes
    name-to-tag         updates id3 tag v2 from filename (according to kaudiobooks own filename pattern)
    tag-to-dirname      renames directories from the tags of the chapter mp3s inside it
    dirname-to-tag      updates mp3 tags from parent directory name (using kaudiobook' own filename pattern)
    sanitize-dirnames   renames audiobook directories replacing problematic characters with unicode lookalikes (ignores directories that don't contain audiobook chapters [mp3 files])
    overwrite-title-from-track
                        sets the track number as title in the format: [ 1 ]

options:
  -h, --help            show this help message and exit
```