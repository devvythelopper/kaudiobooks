
import traceback
import os
import sys
import argparse
import asyncio
from kpyutils.tree import *
from kpyutils.cli import *
import subprocess
from datetime import datetime
from audible_cli.models import Library
from audible_cli.config import Session
import logging
import concurrent
import eyed3
from natsort import natsorted
import re

log = logging.getLogger(__name__)

def ensure_audible_dir(args):
   if args.audible_dir is None:
      raise ValueError("either --audible-dir or KAUDIOBOOKS_AUDIBLE_DIR must be set")

def make_date_args(args):
   
  start = ""
  end = ""
  if args.start_date is not None:
    start = f'--start-date "{args.start_date}"'
  if args.end_date is not None:
    end = f'--end-date "{args.start_end}"'
  return f' {start} {end}'

def download(args):
  ensure_audible_dir(args)
  date_args = make_date_args(args)
  
  subprocess.run(f"audible download --output-dir '{args.audible_dir}' --pdf --cover --annotation --chapter --chapter-type Flat --quality best --aaxc --all {date_args}", shell=True)


def sanitize_filename(filename):
    replacements = {
        '\\': '＼',
        '/': '／',
        ':': '꞉',
        '*': '＊',
        '?': '？',
        '"': '＂',
        '<': '＜',
        '>': '＞',
        '|': '｜',
        '\0': '',  # Remove null character
    }
    return ''.join(replacements.get(c, c) for c in filename)

def unsanitize_filename(sanitized_filename):
    replacements = {
        '＼': '\\',
        '／': '/',
        '꞉': ':',
        '＊': '*',
        '？': '?',
        '＂': '"',
        '＜': '<',
        '＞': '>',
        '｜': '|',
    }
    return ''.join(replacements.get(c, c) for c in sanitized_filename)


# Example usage:
# sanitized = sanitize_filename('example:filename?.txt')


def is_chapter_file(path):
  return path.endswith(".mp3")



def show_string_diff(str1, str2):
  for i, (c1, c2) in enumerate(zip(str1, str2)):
    if c1 != c2:
        log.info(f"Difference at position {i}: '{c1}' vs '{c2}'")
        break
    else:
        if len(str1) != len(str2):
            log.info(f"Difference at position {min(len(str1), len(str2))}: Length mismatch")



filename_pattern = r"^(.+) -- (\d+) -- (.+)\.mp3$"
dir_pattern = r"^(.+) -- (.+)$"




def purge(args):
  def handle_album(album_path):
    log.debug(f"handling album {album_path}")
    is_audiobook = False
    files = list(natsorted(os.listdir(album_path)))
    for f in files:
      if f.endswith(".mp3"):
        is_audiobook = True
        break
    r = []

    def handle_file(f):
      log.debug(f"handling file {f}")
      if f.endswith(".jpg") or f.endswith(".m3u"):
        path = album_path + "/" + f
        def remove():
          os.remove(path)
        log.info(f"deleting file: {path}")
        r.append(remove)

    if is_audiobook:
      log.debug("it is an audiobook")
      for f in files:
        handle_file(f)
    return r
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def name_to_tag(args):


  def handle_album(album_path):
    log.debug(f"handling album: {album_path}")

    files = list(filter(is_chapter_file, natsorted(os.listdir(album_path))))
    
    num_files = len(files)

    digits = len(str(num_files))
    log.debug(f"digits: {digits}")
    index = 0


    def handle_chapter(child):
      path = f"{album_path}/{child}"
      nonlocal index
      index += 1
      log.debug(f"handling chapter: {path}")
        
      name = os.path.basename(path)


      match = re.match(filename_pattern, name)
      if match:
        album = match.group(1)
        track = match.group(2)
        title = match.group(3)

        audiofile = eyed3.load(path)



        change = False


        tag = eyed3.load(path).tag
        

        if args.renumber:
          if tag.track_num[0] != index or tag.track_num[1] != num_files:

            log.info(f"`{child}`: updating track number to: {index}/{num_files}")
            tag.track_num = (index, num_files)
            change = True

        if tag.title != unsanitize_filename(title):
          log.info(f"`{child}`: updating title: `{tag.title}`\n--> `{title}`")
          tag.title = unsanitize_filename(title)
          change = True

        if tag.album != unsanitize_filename(album):
          log.info(f"`{child}`: updating album: `{tag.album}`\n--> `{album}`")
          tag.album = unsanitize_filename(album)
          change = True

        def commit():
          tag.save()
        if change:
          return commit
      
    return list(map(handle_chapter, files))
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def tag_to_dirname(args):

  def handle_album(album_path):
    log.info(f"handling directory: {album_path}")
    is_audiobook = False
    sample = None
    files = list(natsorted(os.listdir(album_path)))
    for f in files:
      if f.endswith(".mp3"):
        sample = f
        is_audiobook = True
        break
    if is_audiobook:
      tag = eyed3.load(f"{album_path}/{sample}").tag
      old_name = os.path.basename(album_path)
      new_name = sanitize_filename(f"{tag.album} -- {tag.artist}")
      if old_name != new_name:
        log.info(f"renaming directory: `{album_path}` --> {new_name}")
        def rename():
          os.rename(album_path, f"{os.path.dirname(old_name)}/{new_name}")
        return rename

  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def sanitize_dir_names(args):
  
  def handle_album(album_path):  
    log.debug(f"handling album {album_path}")
    is_audiobook = False
    files = list(natsorted(os.listdir(album_path)))
    for f in files:
      if f.endswith(".mp3"):
        is_audiobook = True
        break
    if not is_audiobook:
      return
    album_path = album_path.rstrip("/")
    album_name = os.path.basename(album_path)
    album = sanitize_filename(album_name)
    if album_name != album:
      log.info(f"renaming: `{album_name}`\n--> {album}")
      def rename():
        os.rename(album_path, f"{os.path.dirname(album_path)}/{album}")
      return rename
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def overwrite_title_from_track(args):

  def handle_album(album_path):
    log.debug(f"handling album: {album_path}")

    files = list(filter(is_chapter_file, natsorted(os.listdir(album_path))))
    
    num_files = len(files)

    digits = len(str(num_files))
    log.info(f"digits: {digits}")
    index = 0


    def handle_file(child):
      path = f"{album_path}/{child}"
      nonlocal index
      index += 1
      log.debug(f"handling chapter: {path}")
      

      tag = eyed3.load(path).tag

      if args.intro is not None:
        if index == 1:
          tag.title = args.intro
        else:
          tag.title = f"[ {index - 1} ]"
      else:
        tag.title = f"[ {index} ]"

      if args.renumber:
        tag.track_num = (index, num_files)

      chg = name_change_from_tag(digits, path, tag)
      if chg is not None:
        def rename():


          if args.renumber:
            tag.save()
          chg()
        return rename

    
    return list(map(handle_file, files))
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def dirname_to_tag(args):
  
  def handle_album(album_path):
    log.debug(f"handling album {album_path}")
    is_audiobook = False
    files = list(natsorted(os.listdir(album_path)))
    num_files = 0
    for f in files:
      if f.endswith(".mp3"):
        is_audiobook = True
        num_files += 1
    r = []
    album_path = album_path.rstrip("/")
    album_name = os.path.basename(album_path)

    digits = len(str(num_files))

    index = 0

    match = re.match(dir_pattern, album_name)
    if match:
      album = unsanitize_filename(match.group(1))
      author = unsanitize_filename(match.group(2))
    else:
      log.info(f"directory name does not match pattern: {album_name}")
      return

    def handle_file(f):

      nonlocal index
      log.debug(f"handling file {f}")
      if f.endswith(".mp3"):
        path = album_path + "/" + f
        tag = eyed3.load(path).tag

        index += 1

        change = False
        
        if tag.album != album:
          log.info(f"updating album: `{tag.album}`\n--> `{album}`")
          tag.album = album
          change = True

        if tag.artist != author:
          log.info(f"updating artist/author: `{tag.artist}`\n--> `{author}`")
          tag.artist = author
          change = True

        if args.renumber:
          tag.track_num = (index, num_files)

        name_change = None
        if args.rename:
          name_change = name_change_from_tag(digits, path, tag)

        def commit():
          tag.save()
          if name_change is not None:
            name_change()
        if change:
          r.append(commit)
        elif name_change is not None:
          r.append(name_change)

    if is_audiobook:
      log.debug("it is an audiobook")
      for f in files:
        handle_file(f)
    return r
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)


def name_change_from_tag(digits, path, tag):

  title = sanitize_filename(tag.title)
  album = sanitize_filename(tag.album)
  track = str(tag.track_num[0]).zfill(digits)

  new_name = f"{album} -- {track} -- {title}.mp3"
  old_name = os.path.basename(path)
  new_path = f"{os.path.dirname(path)}/{new_name}"


  if old_name != new_name:

    # show_string_diff(path, new_path)
    log.info(f"rename: `{old_name}`\n--> `{new_name}")
    def rename():
      # rename file path to x
      os.rename(path, new_path)
    return rename


def tag_to_name(args):

  def handle_album(album_path):
    log.debug(f"handling album: {album_path}")

    files = list(filter(is_chapter_file, natsorted(os.listdir(album_path))))
    
    num_files = len(files)

    digits = len(str(num_files))
    log.info(f"digits: {digits}")
    index = 0


    def handle_file(child):
      path = f"{album_path}/{child}"
      nonlocal index
      index += 1
      log.debug(f"handling chapter: {path}")
      

      tag = eyed3.load(path).tag

      if args.renumber:
        tag.track_num = (index, num_files)

      chg = name_change_from_tag(digits, path, tag)
      if chg is not None:
        def rename():


          if args.renumber:
            tag.save()
          chg()
        return rename

    
    return list(map(handle_file, files))
  changes = map_file_tree(args.root, handle_branch=handle_album)
  execute_confirmed_changes(changes)

def execute_confirmed_changes(changes):

  count = 0
  for c in changes:
    if c is not None:
      if isinstance(c, list):
        for e in c:
          if e is not None:
            count += 1
      else:
        count += 1
  if count > 0:
    if confirm("if these changes should be commited type yes: "):
      for c in changes:
        if c is not None:
          if isinstance(c, list):
              for e in c:
                if e is not None:
                  log.info("applying change")
                  e()
          else:
            log.info("applying change")
            c()
  else:
    log.info("nothing to change")


def convert(args):
  return asyncio.run(do_convert(args))

async def do_convert(args):
  ensure_audible_dir(args)
  log.info("loading library")
  lib = await Library.from_api(Session().get_client(), start_date = args.start_date, end_date= args.end_date)
  log.info("items to convert:")
  for item in lib:
     log.info(f"{item.create_base_filename("ascii")}")
  log.info("starting conversion")

  def execute_wrapper(args):
     execute_conversion(*args)

  def execute_conversion(index, item):
    base_filename = item.create_base_filename("ascii")  
    try:
      _, aaxcodec = asyncio.run(item.get_aax_url_old("best"))
    except:
      aaxcodec = ""
    aaxccodec, _ = item._get_codec("best")
    log.info(f"converting {index}: {base_filename}")

    aaxcpath = f"{args.audible_dir}/{base_filename}-{aaxccodec}.aax"
    aaxpath = f"{args.audible_dir}/{base_filename}-{aaxcodec}.aaxc"
    if os.path.isfile(aaxcpath):
      path = aaxcpath
    elif os.path.isfile(aaxpath):
      path = aaxpath
    else:
       raise ValueError(f"audiobook `{base_filename}` does not exist. Download it first.")

    subprocess.run(["aaxtomp3", "--dir-naming-scheme", "$title -- $artist", path])
    # subprocess.run("echo sleeping; sleep 1; echo done;", shell=True)
    log.info(f"conversion {index} finished: {base_filename}")

  with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
    results = list(executor.map(execute_wrapper, enumerate(lib)))




   


def run_command():
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s.%(levelname)s: %(message)s',
    handlers=[
        # logging.FileHandler(logfile_path + datetime.now().strftime("%d-%m-%Y_%H:%M:%S.%f") ),  # File handler
        logging.StreamHandler(sys.stdout)   # Stream handler for stdout
    ]
  )

  parser = argparse.ArgumentParser(description="audiobooks manager")
  subparser = parser.add_subparsers(required=True)


  global_parser = argparse.ArgumentParser(add_help=False)
  global_parser.add_argument("--verbose", action='store_true', help="log debugging stuff")

  audible_parser = argparse.ArgumentParser(add_help=False, parents=[global_parser])
  audible_parser.add_argument("--audible-dir", type=str, help="the path to the audible directory", default=os.getenv("KAUDIOBOOKS_AUDIBLE_DIR"))


  

  purge_parser = subparser.add_parser('purge', parents=[global_parser], help= 'purges all non-audiobook files (non mp3s) from audiobook directories. This gets rid of m3u and cover.jpg for example. Will only delete files from directories that actually contain audiobook files (mp3 files)')
  purge_parser.add_argument("--root", type=str, help="the directory under which the files lay (or just a single file)", default=None)
  purge_parser.set_defaults(func=purge)





  dated_parser = argparse.ArgumentParser(add_help=False)
  dated_parser.add_argument("--start-date", type=date_or_datetime, help="only convert audiobooks added on or after", default=None)
  dated_parser.add_argument("--end-date", type=date_or_datetime, help="only convert audiobooks added on or before", default=None)



  download_parser = subparser.add_parser('download', parents=[audible_parser, dated_parser], help= 'downloads all audiobooks (that are not already present in the audible directory)')
  download_parser.set_defaults(func=download)


  convert_parser = subparser.add_parser('convert', parents=[audible_parser, dated_parser], help= 'converts audiobooks')
  convert_parser.add_argument("--jobs", type=int, help="the number of jobs", default=2)


  tag_to_name_parser = subparser.add_parser('tag-to-name', parents=[global_parser], help= 'renames audiobook files from mp3 tags (only using tag version 2) replacing problematic characters with unicode lookalikes')
  tag_to_name_parser.add_argument("--root", type=str, help="the directory under which the files lay (or just a single file)", default=None)
  tag_to_name_parser.add_argument("--renumber", action='store_true', help="whether the track number should be updated according to sort order of the original files in the directory")
  tag_to_name_parser.set_defaults(func=tag_to_name)


  name_to_tag_parser = subparser.add_parser('name-to-tag', parents=[global_parser], help= 'updates id3 tag v2 from filename (according to kaudiobooks own filename pattern)')
  name_to_tag_parser.add_argument("--root", type=str, help="the directory under which the files lay (or just a single file)", default=None)
  name_to_tag_parser.add_argument("--renumber", action='store_true', help="whether the track number should be updated according to sort order of the original files in the directory")
  name_to_tag_parser.set_defaults(func=name_to_tag)


  tag_to_dirname_parser = subparser.add_parser('tag-to-dirname', parents=[global_parser], help= 'renames directories from the tags of the chapter mp3s inside it')
  tag_to_dirname_parser.add_argument("--root", type=str, help="the directory under which the audiobook directories lay (or just a single directories)", default=None)
  tag_to_dirname_parser.set_defaults(func=tag_to_dirname)

  dirname_to_tag_parser = subparser.add_parser('dirname-to-tag', parents=[global_parser], help= 'updates mp3 tags from parent directory name (using kaudiobook\' own filename pattern)')
  dirname_to_tag_parser.add_argument("--rename", action='store_true', help="whether to also rename the chapter files if the tag changed")
  dirname_to_tag_parser.add_argument("--renumber", action='store_true', help="whether the track number should be updated according to sort order of the original files in the directory")
  dirname_to_tag_parser.add_argument("--root", type=str, help="the directory under which the audiobook directories lay (or just a single directories)", default=None)


  sanitize_dir_names_parser = subparser.add_parser('sanitize-dirnames', parents=[global_parser], help= 'renames audiobook directories replacing problematic characters with unicode lookalikes (ignores directories that don\'t contain audiobook chapters [mp3 files])')
  sanitize_dir_names_parser.add_argument("--root", type=str, help="the directory under which the audiobook directories lay (or just a single directories)", default=None)
  sanitize_dir_names_parser.set_defaults(func=sanitize_dir_names)

  overwrite_title_from_track_parser = subparser.add_parser('overwrite-title-from-track', parents=[global_parser], help= 'sets the track number as title in the format: [ 1 ]')
  overwrite_title_from_track_parser.add_argument("--root", type=str, help="the directory under which the audiobook directories lay (or just a single directories)", default=None)
  overwrite_title_from_track_parser.add_argument("--renumber", action='store_true', help="whether the track number should be updated according to sort order of the original files in the directory")
  overwrite_title_from_track_parser.add_argument("--intro", type=str, default=None, help="assume the first track to be an introduction of some sorts, so that counting starts with the second chapter")

  overwrite_title_from_track_parser.set_defaults(func=overwrite_title_from_track)


  dirname_to_tag_parser.set_defaults(func=dirname_to_tag)

  convert_parser.set_defaults(func=convert)

  parser.parse_args()
  
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)
  else:
    logging.getLogger("eyed3.mp3.headers").setLevel(logging.CRITICAL)

  args.func(args)


def date_or_datetime(value):
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Not a valid date or datetime: '{value}'.")


def main():
  run_command()