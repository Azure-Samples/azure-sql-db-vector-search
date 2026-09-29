import argparse
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import struct
import sys
import time
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


SIZES = {"10M": 10_000_000, "100M": 98_735_605}
BASE_URL = "https://comp21storage.z5.web.core.windows.net/yfcc100m_images/"
QUERY_FILE = "yfcc100m_query_vecs.fbin"
FILES = {
    "10M": ("yfcc100m_vecs_sampled_10m.fbin", "yfcc100m_query_gt100_sampled_10m.bin"),
    "100M": ("yfcc100m_vecs.fbin", "yfcc100m_query_gt100.bin"),
}
CHUNK_BYTES = 1024 * 1024
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def get_yfcc_urls(size):
    size = size.upper()
    if size not in FILES:
        raise ValueError("Choose a supported YFCC Images size: 10M or 100M.")
    base_file, ground_truth_file = FILES[size]
    return {
        "base": urljoin(BASE_URL, base_file),
        "queries": urljoin(BASE_URL, QUERY_FILE),
        "ground_truth": urljoin(BASE_URL, ground_truth_file),
    }


def download_file(url, destination):
    destination = Path(destination)
    if destination.exists():
        print(f"Already exists: {destination}")
        return

    partial = destination.with_suffix(destination.suffix + ".part")
    started = time.monotonic()
    last_progress = started
    written = 0
    print(f"Downloading {url} -> {destination}", flush=True)
    with urlopen(url, timeout=60) as source:
        if source.status != 200:
            raise ValueError(f"Expected a complete file response, got HTTP {source.status}")
        length = source.headers.get("Content-Length")
        total = int(length) if length is not None else None
        with partial.open("wb") as output:
            while block := source.read(CHUNK_BYTES):
                output.write(block)
                written += len(block)
                now = time.monotonic()
                if now - last_progress >= 1:
                    total_text = f"{total / 2**20:.2f}" if total is not None else "unknown"
                    print(
                        f"  {written / 2**20:.2f} / {total_text} MiB, "
                        f"{written / 2**20 / (now - started):.2f} MiB/s",
                        flush=True, end="\r",
                    )
                    last_progress = now
        if total is not None and written != total:
            raise ValueError(f"Incomplete download: {destination.name} ({written}/{total} bytes)")
    partial.rename(destination)
    print(f"\nFinished in {time.monotonic() - started:.2f}s: {written:,} bytes", flush=True)


def download_dataset(size, data_dir):
    size = size.upper()
    urls = get_yfcc_urls(size)
    sources = {
        "queries.bin": urls["queries"],
        "groundtruth.bin": urls["ground_truth"],
        "base.bin": urls["base"],
    }
    destination = Path(data_dir) / f"yfcc-images-{size}"
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        if not all((destination / name).is_file() for name in sources):
            raise ValueError(f"Dataset files are missing beside {manifest_path}. Use a new --data-dir.")
        print(f"Already exists: {destination}. Existing files and manifest were left unchanged.")
        return destination

    for filename, url in sources.items():
        if not (destination / filename).exists():
            with urlopen(Request(url, method="HEAD"), timeout=60) as response:
                if response.status != 200:
                    raise ValueError(f"URL check failed for {url}: expected HTTP 200, got {response.status}.")

    files = {}
    for filename, url in sources.items():
        path = destination / filename
        download_file(url, path)
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
            source.seek(0)
            rows, width = struct.unpack("<II", source.read(8))
        files[filename] = {
            "url": url, "bytes": path.stat().st_size, "sha256": digest,
            "rows": rows, "width": width,
        }

    manifest = {
        "version": 1,
        "dataset": f"yfcc-images-{size}",
        "metric": "euclidean",
        "subset": "published sampled corpus" if size != "100M" else "full published corpus",
        "document_count": files["base.bin"]["rows"],
        "dimensions": files["base.bin"]["width"],
        "vector_dtype": "float32",
        "byte_order": "little",
        "query_count": files["queries.bin"]["rows"],
        "ground_truth_k": files["groundtruth.bin"]["width"],
        "checksum_scope": "local files, unchanged from source",
        "files": files,
    }
    partial_manifest = destination / "manifest.json.part"
    with partial_manifest.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")
    partial_manifest.rename(manifest_path)
    print(f"Download complete: {manifest_path}", flush=True)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download YFCC image vectors for MSSQL benchmarks.")
    parser.add_argument("--size", type=str.upper, choices=SIZES, required=True)
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help="Parent directory for yfcc-images-SIZE (default: data beside this script).",
    )
    args = parser.parse_args(argv)
    try:
        download_dataset(args.size, args.data_dir)
    except (OSError, URLError, HTTPException, ValueError, struct.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Download cancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())