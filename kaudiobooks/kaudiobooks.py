
import traceback
import os
import sys
import argparse
import asyncio
import kpyutils.kiify
import subprocess
from datetime import datetime
from audible_cli.models import Library
from audible_cli.config import Session
import logging

log = logging.getLogger(__name__)

def ensure_audible_dir(args):
   if args.audible_dir is None:
      raise ValueError("either --audible-dir or KAUDIOBOOKS_AUDIBLE_DIR must be set")

def download(args):
  ensure_audible_dir(args)
  start = ""
  end = ""
  if args.start_date is not None:
    start = f"--start-date {args.start_date}"
  if args.end_date is not None:
    end = f"--end-date {args.start_end}"

  subprocess.run(f"audible download --output-dir '{args.audible_dir}' --pdf --cover --annotation --chapter --chapter-type Flat --quality best --aaxc --all {start} {end}", shell=True)


def convert(args):
  return asyncio.run(do_convert(args))

async def do_convert(args):
  ensure_audible_dir(args)
  log.info("loading library")
  lib = await Library.from_api(Session().get_client(), start_date = args.start_date, end_date= args.end_date)
  log.info("loaded library")
  for item in lib:
    base_filename = item.create_base_filename("unicode")
    log.info(f"converting: {base_filename}")



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


  shared_parser = argparse.ArgumentParser(add_help=False)
  shared_parser.add_argument("--audible-dir", type=str, help="the path to the audible directory", default=os.getenv("KAUDIOBOOKS_AUDIBLE_DIR"))
  shared_parser.add_argument("--verbose", type=bool, help="log debugging stuff")

  dated_parser = argparse.ArgumentParser(add_help=False)
  dated_parser.add_argument("--start-date", type=date_or_datetime, help="only convert audiobooks added on or after", default=None)
  dated_parser.add_argument("--end-date", type=date_or_datetime, help="only convert audiobooks added on or before", default=None)



  download_parser = subparser.add_parser('download', parents=[shared_parser, dated_parser], help= 'downloads all audiobooks (that are not already present in the audible directory)')
  download_parser.set_defaults(func=download)


  convert_parser = subparser.add_parser('convert', parents=[shared_parser, dated_parser], help= 'converts audiobooks')


  convert_parser.set_defaults(func=convert)

  parser.parse_args()
  
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

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