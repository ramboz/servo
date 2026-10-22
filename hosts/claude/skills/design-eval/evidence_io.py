"""Strict byte identity and closed file inventories for reusable evidence."""

import hashlib
import json
import os
import stat
from contextlib import contextmanager
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


def _file_identity(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@contextmanager
def _regular_file(path):
    require(hasattr(os, "O_NOFOLLOW"), "no-follow file reads unavailable")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "input is not a regular file")
        yield stream
        after = os.fstat(stream.fileno())
        named = os.stat(path, follow_symlinks=False)
        require(
            _file_identity(before) == _file_identity(after) == _file_identity(named),
            "input changed or atomic replacement occurred during read",
        )


def read_bytes(path):
    with _regular_file(path) as stream:
        return stream.read()


def file_hash(path):
    with _regular_file(path) as stream:
        digest = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        return "sha256:" + digest.hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("non-finite JSON: " + value)

    return json.loads(read_bytes(path), object_pairs_hook=pairs, parse_constant=invalid)


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
    rows, identities = [], {root: _file_identity(root.lstat())}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "symlink inventory entry")
        identities[path] = _file_identity(path.lstat())
        if path.is_dir():
            continue
        require(path.is_file(), "unsupported inventory entry")
        name = path.relative_to(root).as_posix()
        safe(root, name)
        rows.append({"path": name, "hash": file_hash(path)})
    require(
        all(_file_identity(path.lstat()) == value for path, value in identities.items()),
        "inventory changed during snapshot",
    )
    return rows
