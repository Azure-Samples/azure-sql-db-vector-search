from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark
import download


def vector_file(rows, dimensions):
    values = [index / 16 for index in range(rows * dimensions)]
    return struct.pack("<II", rows, dimensions) + struct.pack(f"<{len(values)}f", *values)


def ground_truth_file(query_count, depth):
    count = query_count * depth
    return (
        struct.pack("<II", query_count, depth)
        + struct.pack(f"<{count}i", *([0, 1] * query_count))
        + struct.pack(f"<{count}f", *([0.0, 1.0] * query_count))
    )


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(redirect_stderr(io.StringIO()))
        self.sizes = {"10M": 3, "100M": 5}
        self.stack.enter_context(patch.object(download, "CHUNK_BYTES", 16))
        self.bases = {size: vector_file(rows, 3) for size, rows in self.sizes.items()}
        self.queries = vector_file(2, 3)
        self.truth = ground_truth_file(2, 2)
        self.payloads = {
            "/yfcc100m_vecs_sampled_10m.fbin": self.bases["10M"],
            "/yfcc100m_vecs.fbin": self.bases["100M"],
            "/yfcc100m_query_vecs.fbin": self.queries,
            "/yfcc100m_query_gt100_sampled_10m.bin": self.truth,
            "/yfcc100m_query_gt100.bin": self.truth,
        }
        self.requests = []
        self.head_requests = []
        self.http_order = []
        self.head_status = {}
        self.truncate = False
        self.omit_length = False
        self.force_status = None
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_HEAD(self):
                fixture.head_requests.append(self.path)
                fixture.http_order.append("HEAD")
                status = fixture.force_status or fixture.head_status.get(self.path, 200)
                self.send_response(status)
                self.send_header("Content-Length", str(len(fixture.payloads[self.path])))
                self.end_headers()

            def do_GET(self):
                fixture.http_order.append("GET")
                range_header = self.headers.get("Range")
                fixture.requests.append((self.path, range_header))
                if fixture.force_status:
                    self.send_error(fixture.force_status)
                    return
                payload = fixture.payloads[self.path]
                self.send_response(200)
                if not fixture.omit_length:
                    self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if fixture.truncate:
                    payload = payload[:-3]
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.stack.enter_context(patch.object(
            download, "BASE_URL", f"http://127.0.0.1:{self.server.server_port}/"
        ))

    def assert_download(self, size, parent):
        destination = download.download_dataset(size, parent)
        rows = self.sizes[size]
        self.assertEqual((destination / "base.bin").read_bytes(), self.bases[size])
        self.assertEqual((destination / "queries.bin").read_bytes(), self.queries)
        self.assertEqual((destination / "groundtruth.bin").read_bytes(), self.truth)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["document_count"], rows)
        self.assertEqual(manifest["query_count"], 2)
        self.assertEqual(manifest["ground_truth_k"], 2)
        self.assertEqual(manifest["metric"], "euclidean")
        self.assertEqual(manifest["dataset"], f"yfcc-images-{size}")
        for filename, metadata in manifest["files"].items():
            payload = (destination / filename).read_bytes()
            self.assertEqual(metadata["bytes"], len(payload))
            self.assertEqual(metadata["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertFalse(list(destination.glob("*.part")))
        return destination

    def test_all_sizes_use_separate_corpus_and_matching_ground_truth(self):
        names = {
            "10M": ("yfcc100m_vecs_sampled_10m.fbin", "yfcc100m_query_gt100_sampled_10m.bin"),
            "100M": ("yfcc100m_vecs.fbin", "yfcc100m_query_gt100.bin"),
        }
        for size, (base_name, truth_name) in names.items():
            with self.subTest(size=size):
                self.requests.clear()
                self.head_requests.clear()
                self.http_order.clear()
                self.assert_download(size, self.root)
                self.assertEqual(self.requests, [
                    ("/yfcc100m_query_vecs.fbin", None), (f"/{truth_name}", None),
                    (f"/{base_name}", None),
                ])
                self.assertEqual(self.head_requests, ["/yfcc100m_query_vecs.fbin", f"/{truth_name}", f"/{base_name}"])
                self.assertEqual(self.http_order, ["HEAD", "HEAD", "HEAD", "GET", "GET", "GET"])

    def test_labels_record_actual_published_counts(self):
        self.assertEqual(download.SIZES, {"10M": 10_000_000, "100M": 98_735_605})

    def test_missing_content_length(self):
        self.omit_length = True
        self.assert_download("10M", self.root)

    def test_completed_dataset_is_skipped_without_rewriting_manifest(self):
        destination = self.assert_download("10M", self.root)
        manifest = (destination / "manifest.json").read_bytes()
        self.requests.clear()
        self.head_requests.clear()
        download.download_dataset("10M", self.root)
        self.assertEqual((destination / "manifest.json").read_bytes(), manifest)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.head_requests, [])

    def test_existing_file_is_skipped(self):
        path = self.root / "queries.bin"
        path.write_bytes(self.queries)
        download.download_file(download.get_yfcc_urls("10M")["queries"], path)
        self.assertEqual(path.read_bytes(), self.queries)
        self.assertEqual(self.requests, [])

    def test_partial_file_restarts_on_next_invocation(self):
        destination = self.root / "yfcc-images-10M"
        destination.mkdir()
        (destination / "queries.bin.part").write_bytes(b"interrupted bytes")
        self.assert_download("10M", self.root)

    def test_completed_files_survive_failure_and_are_skipped_on_rerun(self):
        self.payloads["/yfcc100m_query_gt100_sampled_10m.bin"] = b"short"
        self.assertEqual(download.main(["--size", "10M", "--data-dir", str(self.root)]), 1)
        destination = self.root / "yfcc-images-10M"
        self.assertEqual((destination / "queries.bin").read_bytes(), self.queries)
        self.assertFalse((destination / "manifest.json").exists())
        (destination / "groundtruth.bin").unlink()
        self.payloads["/yfcc100m_query_gt100_sampled_10m.bin"] = self.truth
        self.requests.clear()
        self.assert_download("10M", self.root)
        self.assertNotIn(("/yfcc100m_query_vecs.fbin", None), self.requests)

    def test_existing_manifest_with_missing_files_is_not_replaced(self):
        destination = self.assert_download("10M", self.root)
        manifest = (destination / "manifest.json").read_bytes()
        (destination / "base.bin").unlink()
        self.requests.clear()
        with self.assertRaisesRegex(ValueError, "Dataset files are missing"):
            download.download_dataset("10M", self.root)
        self.assertEqual((destination / "manifest.json").read_bytes(), manifest)
        self.assertEqual(self.requests, [])

    def test_unexpected_partial_http_response_is_not_published(self):
        response = io.BytesIO(self.queries)
        response.status = 206
        with patch.object(download, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "complete file response"):
                download.download_file("https://example.invalid/queries", self.root / "queries.bin")
        self.assertFalse((self.root / "queries.bin").exists())
        self.assertFalse((self.root / "queries.bin.part").exists())

    def test_non_200_get_preserves_existing_partial_file(self):
        partial = self.root / "queries.bin.part"
        partial.write_bytes(b"earlier partial")
        for status in (204, 206):
            response = io.BytesIO(self.queries)
            response.status = status
            with self.subTest(status=status), patch.object(download, "urlopen", return_value=response):
                with self.assertRaisesRegex(ValueError, "complete file response"):
                    download.download_file("https://example.invalid/queries", self.root / "queries.bin")
                self.assertEqual(partial.read_bytes(), b"earlier partial")

    def test_header_is_recorded_without_rewriting(self):
        self.bases["10M"] = vector_file(4, 3)
        self.sizes["10M"] = 4
        self.payloads["/yfcc100m_vecs_sampled_10m.fbin"] = self.bases["10M"]
        self.assert_download("10M", self.root)

    def test_truncated_payload_is_not_published(self):
        self.truncate = True
        with self.assertRaisesRegex(ValueError, "Incomplete download"):
            download.download_dataset("10M", self.root)
        destination = self.root / "yfcc-images-10M"
        self.assertTrue((destination / "queries.bin.part").exists())
        self.assertFalse((destination / "queries.bin").exists())
        self.assertFalse((destination / "manifest.json").exists())

    def test_download_copies_arbitrary_bytes_without_format_conversion(self):
        payload = bytes(range(256)) * 3
        self.payloads["/raw.bin"] = payload
        download.download_file(download.BASE_URL + "raw.bin", self.root / "raw.bin")
        self.assertEqual((self.root / "raw.bin").read_bytes(), payload)

    def test_progress_reports_bytes_and_speed(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(download.time, "monotonic", side_effect=range(100)):
            download.download_file(download.get_yfcc_urls("10M")["queries"], self.root / "queries.bin")
        self.assertIn("MiB/s", output.getvalue())
        self.assertIn(f"{len(self.queries):,} bytes", output.getvalue())

    def test_cli_accepts_lowercase_size(self):
        self.assertEqual(benchmark.main(["download", "--size", "10m", "--data-dir", str(self.root)]), 0)

    def test_cli_rejects_unsupported_size_before_downloading(self):
        for size in ("1M", "1m", "500K"):
            with self.subTest(size=size), self.assertRaises(SystemExit) as caught:
                benchmark.main(["download", "--size", size, "--data-dir", str(self.root)])
            self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.head_requests, [])
        self.assertFalse(list(self.root.iterdir()))

    def test_cli_reports_http_error_without_retry(self):
        self.force_status = 503
        self.assertEqual(benchmark.main(["download", "--size", "10M", "--data-dir", str(self.root)]), 1)
        self.assertEqual(len(self.head_requests), 1)
        self.assertEqual(self.requests, [])
        self.assertFalse((self.root / "yfcc-images-10M/manifest.json").exists())

    def test_every_url_is_checked_before_any_download(self):
        for status in (204, 206, 404, 405):
            with self.subTest(status=status):
                self.head_requests.clear()
                self.head_status["/yfcc100m_vecs_sampled_10m.fbin"] = status
                self.assertEqual(download.main(["--size", "10M", "--data-dir", str(self.root)]), 1)
                self.assertEqual(len(self.head_requests), 3)
                self.assertEqual(self.requests, [])
                self.assertFalse(list((self.root / "yfcc-images-10M").iterdir()))

    def test_direct_api_rejects_unsupported_size_before_output_or_requests(self):
        for size in ("1M", "1m", "500k"):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "supported"):
                download.download_dataset(size, self.root)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.head_requests, [])
        self.assertFalse(list(self.root.iterdir()))

    def test_direct_api_accepts_lowercase_size(self):
        self.assertEqual(download.download_dataset("10m", self.root), self.root / "yfcc-images-10M")

    def test_removed_1m_leaves_existing_downloads_and_results_unchanged(self):
        existing = self.root / "yfcc-images-1M"
        existing.mkdir()
        artifacts = {"base.bin": b"existing vectors", "manifest.json": b"existing manifest",
                     "queries.csv": b"existing results"}
        for name, payload in artifacts.items():
            (existing / name).write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "supported"):
            download.download_dataset("1M", self.root)
        for name, payload in artifacts.items():
            self.assertEqual((existing / name).read_bytes(), payload)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.head_requests, [])

    def test_preflight_skips_completed_files_and_preserves_partials_on_failure(self):
        destination = self.root / "yfcc-images-10M"
        destination.mkdir()
        (destination / "queries.bin").write_bytes(self.queries)
        partial = destination / "base.bin.part"
        partial.write_bytes(b"earlier partial")
        self.head_status["/yfcc100m_vecs_sampled_10m.fbin"] = 404
        self.assertEqual(download.main(["--size", "10M", "--data-dir", str(self.root)]), 1)
        self.assertNotIn("/yfcc100m_query_vecs.fbin", self.head_requests)
        self.assertEqual(self.requests, [])
        self.assertEqual(partial.read_bytes(), b"earlier partial")
        self.assertEqual((destination / "queries.bin").read_bytes(), self.queries)

    def test_cli_reports_interrupted_http_read(self):
        with patch.object(download, "download_file", side_effect=IncompleteRead(b"partial")) as download_mock:
            self.assertEqual(benchmark.main(["download", "--size", "10M", "--data-dir", str(self.root)]), 1)
        download_mock.assert_called_once()
        self.assertFalse((self.root / "yfcc-images-10M/manifest.json").exists())

    def test_cli_handles_cancellation_without_retry(self):
        with patch.object(download, "download_file", side_effect=KeyboardInterrupt) as download_mock:
            self.assertEqual(benchmark.main(["download", "--size", "10M", "--data-dir", str(self.root)]), 130)
        download_mock.assert_called_once()
        self.assertFalse((self.root / "yfcc-images-10M/manifest.json").exists())

    def test_download_stage_runs_directly(self):
        self.assertEqual(download.main(["--size", "10m", "--data-dir", str(self.root)]), 0)
        self.assertTrue((self.root / "yfcc-images-10M/manifest.json").exists())

    def test_dispatcher_forwards_arguments_and_exit_status(self):
        stage_args = ["--size", "10M", "--data-dir", str(self.root)]
        with patch.object(download, "main", return_value=130) as stage_main:
            self.assertEqual(benchmark.main(["download", *stage_args]), 130)
        stage_main.assert_called_once_with(stage_args)
        self.assertEqual(self.requests, [])

    def test_dispatcher_download_help_uses_stage_options(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            benchmark.main(["download", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("--size", output.getvalue())
        self.assertIn("--data-dir", output.getvalue())
        self.assertEqual(self.requests, [])


class UrlTests(unittest.TestCase):
    def test_exact_published_urls_and_shared_queries(self):
        base_url = "https://comp21storage.z5.web.core.windows.net/yfcc100m_images/"
        expected = {
            "10M": ("yfcc100m_vecs_sampled_10m.fbin", "yfcc100m_query_gt100_sampled_10m.bin"),
            "100M": ("yfcc100m_vecs.fbin", "yfcc100m_query_gt100.bin"),
        }
        self.assertEqual(download.BASE_URL, base_url)
        for size, (corpus, truth) in expected.items():
            with self.subTest(size=size):
                self.assertEqual(download.get_yfcc_urls(size.lower()), {
                    "base": base_url + corpus,
                    "queries": base_url + "yfcc100m_query_vecs.fbin",
                    "ground_truth": base_url + truth,
                })

    def test_unsupported_size_is_rejected(self):
        for size in ("1M", "1m", "500K"):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "supported"):
                download.get_yfcc_urls(size)

    def test_supported_sizes_exclude_1m(self):
        self.assertEqual(download.SIZES, {"10M": 10_000_000, "100M": 98_735_605})
        self.assertEqual(set(download.FILES), set(download.SIZES))

    def test_all_stage_clis_reject_1m_and_advertise_only_supported_sizes(self):
        root = Path(download.__file__).resolve().parent
        for stage in ("download", "load", "build", "search"):
            script = root / f"{stage}.py"
            with self.subTest(stage=stage, option="--help"):
                help_result = subprocess.run([sys.executable, str(script), "--help"],
                                             capture_output=True, text=True, check=True, timeout=15)
                self.assertIn("--size {10M,100M}", help_result.stdout)
            for size in ("1M", "1m"):
                with self.subTest(stage=stage, size=size):
                    result = subprocess.run([sys.executable, str(script), "--size", size],
                                            capture_output=True, text=True, check=False, timeout=15)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("invalid choice: '1M'", result.stderr)


if __name__ == "__main__":
    unittest.main()