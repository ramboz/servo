"""Closed multi-resource local snapshot; no backend or arbitrary HTTP attestation."""

import os
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "servo-snapshot-source-only-" + str(os.getpid())
    )
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import http.server
import re
import threading
from contextlib import contextmanager
from pathlib import Path

import evidence_io as bundle
from evidence_io import file_hash, inventory, load, require, safe


def configuration(source):
    config = load(safe(source, "candidate.json"))
    require(
        set(config) == {"schema_version", "kind", "entry", "resources", "metadata"}
        and type(config["schema_version"]) is int
        and config["schema_version"] == 1
        and config["kind"] == "static_snapshot_candidate",
        "unsupported snapshot candidate",
    )
    routes = config["resources"]
    require(type(routes) is list and bool(routes), "missing snapshot routes")
    urls, paths = [], []
    for row in routes:
        require(
            type(row) is dict and set(row) == {"url", "path", "content_type"},
            "unsupported snapshot resource",
        )
        url = row["url"]
        require(
            type(url) is str and re.fullmatch(r"/[A-Za-z0-9_./-]+", url), "unsupported snapshot URL"
        )
        safe(source, url[1:])
        safe(source, row["path"])
        require(
            row["content_type"]
            in (
                "text/html",
                "text/javascript",
                "text/css",
                "application/json",
                "text/html; charset=utf-8",
                "text/javascript; charset=utf-8",
                "application/json; charset=utf-8",
            ),
            "unsupported snapshot content type",
        )
        urls.append(url)
        paths.append(row["path"])
    require(
        urls == sorted(set(urls)) and len(set(paths)) == len(paths),
        "duplicate/unsorted snapshot resources",
    )
    require(config["entry"] in urls, "missing snapshot entry")
    require(
        next(row["content_type"] for row in routes if row["url"] == config["entry"]).split(";")[0]
        == "text/html",
        "snapshot entry is not HTML",
    )
    metadata = config["metadata"]
    require(
        type(metadata) is list and metadata == sorted(set(metadata)), "invalid snapshot metadata"
    )
    for name in metadata:
        safe(source, name)
    expected = sorted(["candidate.json", *paths, *metadata])
    require(len(expected) == len(set(expected)), "aliased snapshot input")
    require(
        [row["path"] for row in inventory(source)] == expected, "snapshot input closure mismatch"
    )
    return config


def build(source, destination):
    source, destination = Path(source), Path(destination)
    require(not source.is_symlink(), "symlink snapshot source")
    source = source.resolve()
    require(not destination.resolve().is_relative_to(source), "source/output overlap")
    config = configuration(source)
    inputs = inventory(source)
    bodies = {
        row["path"]: bundle.read_bytes(safe(source, row["path"])) for row in config["resources"]
    }
    require(inventory(source) == inputs, "snapshot source changed during read")
    destination.mkdir()
    output = destination / "output"
    output.mkdir()
    for name, body in bodies.items():
        path = safe(output, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    recipe = {"path": str(Path(__file__).resolve()), "hash": file_hash(__file__)}
    outputs = inventory(output)
    record = {
        "schema_version": 1,
        "kind": "static_snapshot_build",
        "source": str(source),
        "inputs": inputs,
        "outputs": outputs,
        "configuration": config,
        "recipe": recipe,
        "input_hash": bundle.identity(
            "servo-static-snapshot-input-v1", {"files": inputs, "recipe": recipe}
        ),
        "output_hash": bundle.identity("servo-static-snapshot-output-v1", outputs),
    }
    require(inventory(source) == inputs, "snapshot source changed during build")
    bundle.publish(destination / "build.json", record)
    return record


def verify(record, build_root, delivery):
    require(
        type(record) is dict
        and set(record)
        == {
            "schema_version",
            "kind",
            "source",
            "inputs",
            "outputs",
            "configuration",
            "recipe",
            "input_hash",
            "output_hash",
        }
        and type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["kind"] == "static_snapshot_build",
        "unsupported snapshot build",
    )
    source = Path(record["source"])
    require(configuration(source) == record["configuration"], "snapshot configuration changed")
    require(inventory(source) == record["inputs"], "snapshot inputs changed")
    require(
        record["recipe"] == {"path": str(Path(__file__).resolve()), "hash": file_hash(__file__)},
        "snapshot build recipe changed",
    )
    require(
        record["input_hash"]
        == bundle.identity(
            "servo-static-snapshot-input-v1",
            {"files": record["inputs"], "recipe": record["recipe"]},
        ),
        "snapshot input identity mismatch",
    )
    require(
        record["output_hash"]
        == bundle.identity("servo-static-snapshot-output-v1", record["outputs"]),
        "snapshot output identity mismatch",
    )
    require(
        inventory(Path(build_root) / "output") == record["outputs"], "snapshot build output changed"
    )
    require(inventory(delivery) == record["outputs"], "snapshot current delivery mismatch")
    inputs = {row["path"]: row["hash"] for row in record["inputs"]}
    require(
        record["outputs"]
        == [
            {"path": name, "hash": inputs[name]}
            for name in sorted(row["path"] for row in record["configuration"]["resources"])
        ],
        "snapshot copy-output closure mismatch",
    )
    return record


@contextmanager
def serve(record, build_root):
    routes = {
        row["url"]: {
            **row,
            "body": bundle.read_bytes(safe(Path(build_root) / "output", row["path"])),
        }
        for row in record["configuration"]["resources"]
    }
    expected = {row["path"]: row["hash"] for row in record["outputs"]}
    require(
        all(bundle.raw(row["body"]) == expected[row["path"]] for row in routes.values()),
        "snapshot served resource changed",
    )

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in routes:
                self.send_error(404)
                return
            row = routes[self.path]
            self.send_response(200)
            self.send_header("Content-Type", row["content_type"])
            self.send_header("Content-Length", str(len(row["body"])))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(row["body"])

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", routes
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        require(not thread.is_alive(), "snapshot server cleanup unavailable")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "verify"))
    for name in ("source", "out", "build", "delivery"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "build":
            require(
                args.source is not None and args.out is not None,
                "snapshot source and output required",
            )
            record = build(args.source, args.out)
        else:
            require(
                args.build is not None and args.delivery is not None,
                "snapshot build and delivery required",
            )
            record = verify(bundle.load(args.build / "build.json"), args.build, args.delivery)
        print(
            bundle.canonical(
                {
                    "input_hash": record["input_hash"],
                    "output_hash": record["output_hash"],
                    "claim": "closed-local-snapshot-not-backend-authenticity",
                }
            ).decode()
        )
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("REFUSE static snapshot: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
