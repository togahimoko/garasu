#!/usr/bin/env python3
"""Reproducible offline candidate release; atomic local promotion and rollback.

This tool does NOT publish to GitHub or modify live Remnawave/SRR subscriptions.
Atomic means one same-filesystem CURRENT.json pointer, not remote HTTP caches.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from scripts import unified_policy, verify_unified_git_objects

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "CURRENT.json"
SHA = re.compile(r"^[a-f0-9]{64}$")
RELEASE_NAME = re.compile(r"^garasu-unified-[a-f0-9]{64}[.]zip$")
GENERATION = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _source_entries(root):
    root = Path(root).resolve()
    policy = unified_policy.load_policy(root / "policy/unified-v1.json")
    lock = unified_policy.load_release_lock(root / "policy/unified-release-lock.json",
                                            policy)
    verify_unified_git_objects.verify_history(root, lock)
    paths = ("policy/unified-v1.json", "policy/unified-release-lock.json")
    result = {}
    for path in sorted(set(paths) | set(lock["assets"])):
        source = (root / path).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("Unsafe or missing candidate input path")
        if path in lock["assets"]:
            result[path] = verify_unified_git_objects._git(
                root, "cat-file", "blob", lock["assets"][path]["git_blob"])
        else:
            result[path] = source.read_bytes()
    candidates = unified_policy.build_candidates(root, policy)
    candidates["clients/unified/mihomo-ru-tld-verified.yaml"] = (
        unified_policy.build_ru_tld_mihomo_candidate(root, policy))
    for path, contents in candidates.items():
        if path in result or not path.startswith("clients/unified/"):
            raise ValueError("Unexpected candidate profile output")
        result[path] = contents.encode("utf-8")
    if len(result) != len(lock["assets"]) + len(paths) + 8:
        raise ValueError("Incomplete or duplicate candidate release inputs")
    return result, lock


def _archive(root, generation="candidate"):
    if not isinstance(generation, str) or not GENERATION.fullmatch(generation):
        raise ValueError("Unsafe candidate generation label")
    entries, lock = _source_entries(root)
    manifest = {
        "schema_version": 1,
        "release_id": lock["release_id"],
        "generation": generation,
        "assets": {
            path: {"bytes": len(content), "sha256": _digest(content)}
            for path, content in sorted(entries.items())
        },
    }
    entries["bundle-manifest.json"] = _json(manifest)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=True) as archive:
        for path in sorted(entries):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 << 16)
            info.create_system = 3
            archive.writestr(info, entries[path], compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    content = out.getvalue()
    _verify_archive(content)
    return content


def _verify_archive(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or "bundle-manifest.json" not in names:
                raise ValueError("Duplicate or missing bundle manifest")
            manifest = json.loads(archive.read("bundle-manifest.json"))
            if manifest.get("schema_version") != 1:
                raise ValueError("Unsupported candidate bundle schema")
            assets = manifest.get("assets")
            if not isinstance(assets, dict) or set(assets) != set(names) - {
                    "bundle-manifest.json"}:
                raise ValueError("Incomplete bundle asset index")
            for name in names:
                if (name.startswith("/") or "\\" in name
                        or any(p in (".", "..", "") for p in Path(name).parts)):
                    raise ValueError("Unsafe archive entry")
            for name, meta in assets.items():
                data = archive.read(name)
                if len(data) != meta["bytes"] or _digest(data) != meta["sha256"]:
                    raise ValueError("Candidate bundle asset integrity mismatch")
            return manifest
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Corrupt candidate release archive") from exc


def _atomic_write(path, data):
    path = Path(path)
    descriptor, temp = tempfile.mkstemp(prefix=".garasu-stage-",
                                        suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _atomic_current(directory, content):
    _atomic_write(Path(directory) / CURRENT, _json(content))


def _validate_pointer(entry):
    if not isinstance(entry, dict) or set(entry) != {"file", "sha256"}:
        raise ValueError("Invalid release pointer")
    if not isinstance(entry["file"], str) or not RELEASE_NAME.fullmatch(entry["file"]):
        raise ValueError("Unsafe release pointer filename")
    if not isinstance(entry["sha256"], str) or not SHA.fullmatch(entry["sha256"]):
        raise ValueError("Invalid release pointer checksum")
    if entry["file"] != "garasu-unified-" + entry["sha256"] + ".zip":
        raise ValueError("Release pointer name/checksum mismatch")


def read_current(directory):
    path = Path(directory) / CURRENT
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("No valid current release pointer") from exc
    if (not isinstance(state, dict) or set(state) != {
            "schema_version", "active", "previous"} or state["schema_version"] != 1):
        raise ValueError("Unsupported or malformed release pointer")
    _validate_pointer(state["active"])
    if state["previous"] is not None:
        _validate_pointer(state["previous"])
    return state


def _verify_pointer(directory, pointer):
    _validate_pointer(pointer)
    path = Path(directory) / pointer["file"]
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError("Referenced candidate release unavailable") from exc
    if _digest(data) != pointer["sha256"]:
        raise ValueError("Referenced candidate release SHA256 mismatch")
    _verify_archive(data)
    return path


def verify_current(directory):
    state = read_current(directory)
    _verify_pointer(directory, state["active"])
    return {"status": "verified", "release": state["active"]["file"]}


def publish(root, directory, *, generation="candidate"):
    """Stage and verify ZIP first; only then atomically replace CURRENT.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise ValueError("Invalid release output directory")
    # Fail closed if an existing pointer references damaged active material.
    try:
        previous_state = read_current(directory)
    except ValueError:
        if (directory / CURRENT).exists():
            raise
        previous_state = None
    if previous_state is not None:
        verify_current(directory)
    blob = _archive(root, generation=generation)
    digest = _digest(blob)
    filename = "garasu-unified-" + digest + ".zip"
    target = directory / filename
    if target.exists():
        _verify_pointer(directory, {"file": filename, "sha256": digest})
    else:
        _atomic_write(target, blob)
    candidate = {"file": filename, "sha256": digest}
    if previous_state is not None and previous_state["active"] == candidate:
        return target
    updated = {"schema_version": 1, "active": candidate, "previous":
               previous_state["active"] if previous_state is not None else None}
    _atomic_current(directory, updated)
    return target


def rollback(directory):
    """Switch CURRENT back only after verifying the existing and older ZIPs."""
    state = read_current(directory)
    verify_current(directory)
    if state["previous"] is None:
        raise ValueError("No previous verified candidate release")
    _verify_pointer(directory, state["previous"])
    new = {"schema_version": 1, "active": state["previous"],
           "previous": state["active"]}
    _atomic_current(directory, new)
    return new["active"]["file"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--publish", action="store_true")
    options.add_argument("--verify", action="store_true")
    options.add_argument("--rollback", action="store_true")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--generation", default="candidate")
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    if args.publish:
        item = publish(ROOT, directory, generation=args.generation)
        print("Published verified offline candidate ZIP:", item.name)
    elif args.verify:
        print(_json(verify_current(directory)).decode("utf-8"), end="")
    else:
        print("Restored previously verified local candidate ZIP:", rollback(directory))
    print("No active panel, subscription or network routes were modified.")


if __name__ == "__main__":
    main()
