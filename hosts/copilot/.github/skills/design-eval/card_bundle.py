"""Closed single-document candidate build and independent delivery identity."""

import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def raw(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(domain, value):
    return raw(domain.encode("ascii") + b"\n" + canonical(value))


def file_hash(path):
    return raw(Path(path).read_bytes())


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("non-finite JSON: " + value)

    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)


def publish(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def safe(root, name):
    require(
        isinstance(name, str) and name and "\\" not in name and ":" not in name,
        "invalid relative path",
    )
    relative = PurePosixPath(name)
    require(
        not relative.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/")),
        "path escape",
    )
    path = Path(root)
    require(not path.is_symlink(), "symlink root")
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), "symlink path")
    require(path.resolve().is_relative_to(Path(root).resolve()), "path escape")
    return path


def inventory(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "missing/symlink directory")
    rows = []
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "symlink inventory entry")
        if path.is_dir():
            continue
        require(path.is_file(), "unsupported inventory entry")
        name = path.relative_to(root).as_posix()
        safe(root, name)
        rows.append({"path": name, "hash": file_hash(path)})
    return rows


class _Document(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for name, _value in attrs:
            require(
                name.lower()
                not in (
                    "src",
                    "srcset",
                    "href",
                    "poster",
                    "data",
                    "action",
                    "formaction",
                    "srcdoc",
                ),
                "unsupported resource attribute: " + name,
            )
        require(
            tag.lower() not in ("iframe", "object", "embed", "base", "link"),
            "unsupported resource element: " + tag,
        )


def source_inventory(source):
    rows = inventory(source)
    require(
        [r["path"] for r in rows] == ["candidate.json", "index.html"],
        "incomplete or extra input closure; expected candidate.json and index.html",
    )
    config = load(safe(source, "candidate.json"))
    require(
        canonical(config)
        == canonical(
            {
                "schema_version": 1,
                "entry": "index.html",
                "dependencies": [],
                "assets": [],
            }
        ),
        "unsupported candidate configuration",
    )
    text = safe(source, "index.html").read_text(encoding="utf-8")
    document = _Document()
    document.feed(text)
    document.close()
    require(
        "url(" not in text.lower() and "@import" not in text.lower(), "unsupported resource CSS"
    )
    return rows


def build(source, destination):
    source, destination = Path(source).resolve(), Path(destination)
    require(not destination.resolve().is_relative_to(source), "source/output overlap")
    inputs = source_inventory(source)
    entry = safe(source, "index.html").read_bytes()
    recipe = {"path": str(Path(__file__).resolve()), "hash": file_hash(__file__)}
    destination.mkdir()
    output = destination / "output"
    output.mkdir()
    (output / "index.html").write_bytes(entry)
    outputs = inventory(output)
    record = {
        "schema_version": 1,
        "kind": "card_candidate_build",
        "source": str(source),
        "inputs": inputs,
        "outputs": outputs,
        "recipe": recipe,
        "input_hash": identity("servo-input-closure-v1", {"files": inputs, "recipe": recipe}),
        "output_hash": identity("servo-output-closure-v1", outputs),
    }
    require(source_inventory(source) == inputs, "source changed during build")
    publish(destination / "build.json", record)
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
            "recipe",
            "input_hash",
            "output_hash",
        },
        "unsupported build contract",
    )
    require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["kind"] == "card_candidate_build",
        "unsupported build version",
    )
    require(
        canonical(load(Path(build_root) / "build.json")) == canonical(record),
        "build manifest changed",
    )
    require(
        record["recipe"]
        == {
            "path": str(Path(__file__).resolve()),
            "hash": file_hash(__file__),
        },
        "build recipe changed",
    )
    require(source_inventory(Path(record["source"])) == record["inputs"], "source changed")
    outputs = inventory(Path(build_root) / "output")
    require(outputs == record["outputs"], "build output changed")
    require(
        record["input_hash"]
        == identity(
            "servo-input-closure-v1",
            {
                "files": record["inputs"],
                "recipe": record["recipe"],
            },
        ),
        "input identity mismatch",
    )
    require(
        record["output_hash"] == identity("servo-output-closure-v1", outputs),
        "output identity mismatch",
    )
    require(inventory(delivery) == outputs, "current delivery mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        record = build(args.source, args.out)
        print(json.dumps(record, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f"REFUSE candidate build: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
