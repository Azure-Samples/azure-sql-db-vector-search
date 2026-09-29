import argparse
from pathlib import Path
import subprocess
import sys

import download



def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an MSSQL vector benchmark stage.")
    commands = parser.add_subparsers(dest="command", required=True)
    download_command = commands.add_parser(
        "download", add_help=False, help="Download a supported YFCC dataset size."
    )
    download_command.set_defaults(handler=download.main)
    commands.add_parser(
        "load", add_help=False, help="Convert and bulk-load a downloaded YFCC dataset."
    )
    commands.add_parser(
        "build", add_help=False, help="Measure one fresh vector index build."
    )
    commands.add_parser(
        "search", add_help=False, help="Measure vector search latency and recall."
    )
    args, stage_args = parser.parse_known_args(argv)
    if args.command in ("load", "build", "search"):
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve().with_name(f"{args.command}.py")), *stage_args],
            check=False,
        ).returncode
    return args.handler(stage_args)


if __name__ == "__main__":
    sys.exit(main())