#!/usr/bin/env python3
"""Verify a NeuralFoil starter ZIP before optional, non-overwriting extraction.

Standard library only. Never imports or executes archive members, opens nested
archives, or displays document/transcript content. Output is confined to this
script's directory. Payload permissions are reset to 0600 (directories 0700),
so executable bits from the uploaded ZIP are not preserved.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import struct
import tempfile
from datetime import datetime, timezone
import unicodedata
import zipfile


STARTER = "NeuralFoil-export-starter-2026-09-06"
FULL = "NeuralFoil-working-folder-export-2026-09-06"
STARTER_MANIFEST = f"{STARTER}/CHECKSUMS-starter.sha256"
FULL_COPY = f"{STARTER}/CHECKSUMS-of-full-archive.sha256"
# Intake found build_export.py covered by the starter manifest but absent from
# the full manifest. This is an explicit coverage exception, not a full-export
# provenance match; it is never executed. Unexpected other extras still fail.
STARTER_ONLY = {STARTER_MANIFEST, f"{STARTER}/README-STARTER.txt", FULL_COPY, f"{STARTER}/build_export.py"}
MAX_FILES = 10000
MAX_EXPANDED = 2 * 1024**3
MAX_FILE = 512 * 1024**2
OUT = Path(__file__).resolve().parent


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name, root, directory=False):
    """Reject unsafe and ambiguously normalized extraction paths."""
    if not name or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError(f"unsafe path characters: {name!r}")
    if name.startswith("/") or PureWindowsPath(name).drive:
        raise ValueError(f"absolute/drive path: {name!r}")
    base = name[:-1] if directory and name.endswith("/") else name
    parts = base.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"empty/dot/traversal component: {name!r}")
    if parts[0] != root or (len(parts) == 1 and not directory):
        raise ValueError(f"unexpected top folder: {name!r}")
    if any(p.endswith((" ", ".")) for p in parts):
        raise ValueError(f"ambiguous trailing character: {name!r}")
    return base


def inspect_member(info):
    key = safe_name(info.filename, STARTER, info.is_dir())
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ValueError(f"link/special file rejected: {info.filename!r}, mode={oct(mode)}")
    if kind == stat.S_IFDIR and not info.is_dir():
        raise ValueError(f"directory mode/name conflict: {info.filename!r}")
    if kind == stat.S_IFREG and info.is_dir():
        raise ValueError(f"regular-file mode/name conflict: {info.filename!r}")
    if info.external_attr & 0x400:
        raise ValueError(f"DOS reparse point rejected: {info.filename!r}")
    if info.flag_bits & 1:
        raise ValueError(f"encrypted member rejected: {info.filename!r}")
    if "session-transcript" in PurePosixPath(key).parts:
        raise ValueError("session-transcript member present: not opened in this intake")
    if info.file_size > MAX_FILE:
        raise ValueError(f"member exceeds safety size limit: {info.filename!r}")
    if info.file_size / max(info.compress_size, 1) > 1000:
        raise ValueError(f"excessive expansion ratio: {info.filename!r}")
    pos = 0
    while pos < len(info.extra):
        if pos + 4 > len(info.extra):
            raise ValueError(f"malformed ZIP extra field: {info.filename!r}")
        field, length = struct.unpack_from("<HH", info.extra, pos)
        pos += 4
        if pos + length > len(info.extra):
            raise ValueError(f"truncated ZIP extra field: {info.filename!r}")
        # These Unix extra fields can encode links. Conservatively reject them.
        if field in (0x000D, 0x756E):
            raise ValueError(f"link-capable Unix extra field rejected: {info.filename!r}")
        pos += length
    return key, mode


def parse_manifest(data, root):
    result = {}
    case_keys = set()
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if not match:
            raise ValueError(f"invalid checksum syntax at line {line_number}")
        digest, name = match.groups()
        safe_name(name, root)
        normalized = unicodedata.normalize("NFC", name).casefold()
        if name in result or normalized in case_keys:
            raise ValueError(f"duplicate checksum path at line {line_number}: {name}")
        case_keys.add(normalized)
        result[name] = digest.lower()
    return result


def essential_files():
    names = [
        "scratchpad/lsat/lsat-nf2.csv", "scratchpad/lsat/lsat-geometry.json",
        "scratchpad/lsat/lsat-geofeat.json", "scratchpad/lsat/lsat-corpus.csv",
        "scratchpad/lsat/lsat-nf.csv", "scratchpad/lsat/lsat-xfoil.csv",
        "scratchpad/lsat/lsat_doubleclean.py", "scratchpad/lsat/lsat_lift_dc.py",
        "scratchpad/lsat/dc-report.txt", "scratchpad/lsat/dc-oof.csv",
        "scratchpad/lsat/dc-by-airfoil.csv", "scratchpad/lsat/dc-measured.json",
        "scratchpad/lsat/dc-lift-report.txt", "scratchpad/lsat/dc-clmax.csv",
        "scratchpad/lsat/dc-correction-cl2.json", "scratchpad/lsat/dc-run.log",
        "scratchpad/lsat/dc-lift-run.log", "scratchpad/lsat/oof2.csv",
        "scratchpad/lsat/oof3.csv", "scratchpad/lsat/correction-cd3.json",
        "scratchpad/lsat/correction-cl2.json", "records/env/pip-freeze-nfenv.txt",
        "records/env/python-version.txt", "records/env/xfoil-build-record.txt",
        "records/env/xfoil/xfoil-binary-linux-x86_64",
        "records/env/xfoil/xfoil-6.99-source-original.tgz", "records/site/git-log.txt",
    ]
    names += [f"scratchpad/lsat/{name}" for name in (
        "volume01.zip", "volume02.zip", "volume03.zip", "volume06.zip",
        "Stec8.zip", "coord_seligFmt.zip")]
    return names


def verify(archive, full_checksums, other_copy=None, extract=False):
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "verifier": str(Path(__file__).resolve()),
        "archive": str(archive), "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha_file(archive),
        "external_full_checksums": str(full_checksums),
        "safety_issues": [], "errors": [], "extracted": False,
        "scope": "Byte-integrity and presence only; no scientific recalculation, nested archive extraction, uploaded-code execution, or transcript reading.",
    }
    external = full_checksums.read_bytes()
    full_manifest = parse_manifest(external, FULL)
    report["external_full_checksums_sha256"] = sha_bytes(external)
    report["full_manifest_entries"] = len(full_manifest)
    if other_copy:
        other = other_copy.read_bytes()
        report["additional_external_copy"] = {
            "path": str(other_copy), "sha256": sha_bytes(other),
            "byte_identical": other == external,
        }
        if other != external:
            report["errors"].append("External full-checksum copies differ")

    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        report["archive_entries"] = len(infos)
        report["directory_entries"] = sum(i.is_dir() for i in infos)
        report["file_entries"] = sum(not i.is_dir() for i in infos)
        report["uncompressed_bytes"] = sum(i.file_size for i in infos)
        if len(infos) > MAX_FILES or report["uncompressed_bytes"] > MAX_EXPANDED:
            raise ValueError("Archive exceeds configured intake size limits")
        keys, normalized_keys, files = {}, {}, {}
        report["duplicate_paths"] = []
        report["case_or_unicode_collisions"] = []
        for info in infos:
            try:
                key, mode = inspect_member(info)
                if key in keys:
                    report["duplicate_paths"].append(key)
                keys[key] = info.is_dir()
                normalized = unicodedata.normalize("NFC", key).casefold()
                if normalized in normalized_keys:
                    report["case_or_unicode_collisions"].append(key)
                normalized_keys[normalized] = key
                if not info.is_dir():
                    files[key] = info
            except ValueError as exc:
                report["safety_issues"].append(str(exc))
        for key in keys:
            for parent in PurePosixPath(key).parents:
                if str(parent) in keys and not keys[str(parent)]:
                    report["safety_issues"].append(f"File/directory prefix collision: {parent}")
        if report["duplicate_paths"] or report["case_or_unicode_collisions"]:
            report["safety_issues"].append("Duplicate/normalization-colliding paths")
        if report["safety_issues"]:
            report["status"] = "FAILED_PRE_READ_SAFETY"
            return report

        # Read each regular member fully: ZipExtFile verifies its stored CRC.
        # Only the checksum text is retained; uploaded programs remain opaque.
        computed, retained = {}, {}
        for name, info in files.items():
            digest, seen = hashlib.sha256(), 0
            chunks = [] if name in (STARTER_MANIFEST, FULL_COPY) else None
            with zf.open(info, "r") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    seen += len(chunk)
                    if seen > info.file_size or seen > MAX_FILE:
                        raise ValueError(f"Expanded byte count exceeded bound: {name}")
                    if chunks is not None:
                        chunks.append(chunk)
            if seen != info.file_size:
                raise ValueError(f"Expanded byte count mismatch: {name}")
            computed[name] = digest.hexdigest()
            if chunks is not None:
                retained[name] = b"".join(chunks)
        report["crc_checked_files"] = len(computed)
        report["crc_failures"] = []
        starter_manifest = parse_manifest(retained[STARTER_MANIFEST], STARTER)
        report["starter_manifest_entries"] = len(starter_manifest)
        report["starter_manifest_sha256"] = sha_bytes(retained[STARTER_MANIFEST])
        report["starter_missing_members"] = sorted(set(starter_manifest) - set(computed))
        report["starter_hash_mismatches"] = [n for n, h in starter_manifest.items() if n in computed and computed[n] != h]
        report["starter_unlisted_members"] = sorted(set(computed) - set(starter_manifest))
        allowed_unlisted = {STARTER_MANIFEST, f"{STARTER}/README-STARTER.txt"}
        report["starter_unexpected_unlisted_members"] = sorted(set(report["starter_unlisted_members"]) - allowed_unlisted)
        report["starter_matching_hashes"] = sum(computed.get(n) == h for n, h in starter_manifest.items())
        report["full_checksum_copies"] = {
            "external_path": str(full_checksums), "internal_member": FULL_COPY,
            "external_bytes": len(external), "internal_bytes": len(retained[FULL_COPY]),
            "external_sha256": sha_bytes(external), "internal_sha256": sha_bytes(retained[FULL_COPY]),
            "byte_identical": external == retained[FULL_COPY],
        }
        if external != retained[FULL_COPY]:
            report["errors"].append("Embedded and external full-checksum copies differ")
        mapped = {n: FULL + n[len(STARTER):] for n in computed}
        report["full_subset_matches"] = [n for n, target in mapped.items() if full_manifest.get(target) == computed[n]]
        report["full_subset_mismatches"] = [n for n, target in mapped.items() if target in full_manifest and full_manifest[target] != computed[n]]
        report["full_subset_unlisted_members"] = [n for n, target in mapped.items() if target not in full_manifest]
        report["full_subset_unexpected_unlisted_members"] = sorted(set(report["full_subset_unlisted_members"]) - STARTER_ONLY)
        report["full_manifest_files_not_in_starter"] = len(set(full_manifest) - set(mapped.values()))
        report["member_hashes"] = computed
        report["essential_file_presence"] = {n: f"{STARTER}/{n}" in files for n in essential_files()}
        report["dc_drag_model_present"] = f"{STARTER}/scratchpad/lsat/dc-correction-cd3.json" in files
        report["nested_archives_present_not_opened"] = [n for n in files if n.lower().endswith((".zip", ".tgz", ".tar.gz"))]
        report["session_transcript_present"] = False
        report["full_subset_builder_exception"] = {
            "member": f"{STARTER}/build_export.py",
            "starter_sha256_verified": computed.get(f"{STARTER}/build_export.py") == starter_manifest.get(f"{STARTER}/build_export.py"),
            "present_in_full_manifest": f"{FULL}/build_export.py" in full_manifest,
            "note": "Packaging script is supplied and starter-checksummed, but neither its mapped path nor its SHA-256 appears in the full manifest. It was not executed or treated as full-export-matched.",
        }
        report["checksum_coverage_note"] = f"{len(starter_manifest)} listed starter files are checked against their SHA-256 manifest. The manifest itself and README-STARTER.txt are unlisted metadata, CRC-checked and locally SHA-256 fingerprinted but not independently covered by that manifest. Four files are absent from the full manifest: those two, CHECKSUMS-of-full-archive.sha256, and build_export.py. The builder is starter-checksummed, but its full-export provenance is not established by the supplied full manifest."
        fatal_fields = (
            "starter_missing_members", "starter_hash_mismatches", "starter_unexpected_unlisted_members",
            "full_subset_mismatches", "full_subset_unexpected_unlisted_members", "errors",
        )
        if any(report[k] for k in fatal_fields) or not all(report["essential_file_presence"].values()):
            report["status"] = "FAILED_INTEGRITY_OR_ESSENTIAL_PRESENCE"
            return report
        report["status"] = "PASS_WITH_DOCUMENTED_CHECKSUM_COVERAGE_EXCEPTIONS"
        if extract:
            # mkdtemp creates a fresh private folder; nothing is overwritten.
            payload = Path(tempfile.mkdtemp(prefix="payload_", dir=OUT))
            payload.chmod(0o700)
            for name, info in files.items():
                target = payload.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                for parent in target.parents:
                    if parent == payload:
                        break
                    if parent.is_symlink():
                        raise ValueError(f"Unexpected symlink in fresh payload: {parent}")
                    parent.chmod(0o700)
                if not target.resolve().is_relative_to(payload):
                    raise ValueError(f"Target escapes payload: {name}")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(target, flags, 0o600)
                with os.fdopen(fd, "wb") as dest, zf.open(info) as src:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dest.write(chunk)
                target.chmod(0o600)
                if sha_file(target) != computed[name]:
                    raise ValueError(f"Post-extraction hash mismatch: {name}")
            report["extracted"] = True
            report["payload_directory"] = str(payload)
            report["post_extraction_matching_hashes"] = len(files)
            report["extraction_permissions"] = "regular files 0600; directories 0700; no uploaded executable bits preserved"
    return report


def report_text(r):
    return "\n".join([
        "# Starter export integrity verification", "", f"Status: {r['status']}", "",
        f"Archive: `{r['archive']}`", f"Archive SHA-256: `{r['archive_sha256']}`", "",
        f"Entries: {r['archive_entries']} ({r['file_entries']} files, {r['directory_entries']} directories); uncompressed bytes: {r['uncompressed_bytes']:,}.",
        f"Path/link/special-file safety issues: {len(r['safety_issues'])}.",
        f"CRC-checked files: {r.get('crc_checked_files', 0)}.",
        f"Starter manifest: {r.get('starter_matching_hashes', 0)} / {r.get('starter_manifest_entries', 0)} matching hashes; missing {len(r.get('starter_missing_members', []))}; mismatches {len(r.get('starter_hash_mismatches', []))}.",
        f"Starter unlisted metadata: {', '.join(r.get('starter_unlisted_members', [])) or 'none'}.",
        f"Full manifest: {r.get('full_manifest_entries', 0)} entries; mapped subset matches {len(r.get('full_subset_matches', []))}; mismatches {len(r.get('full_subset_mismatches', []))}.",
        f"Files absent from full manifest (metadata plus packaging script): {', '.join(r.get('full_subset_unlisted_members', [])) or 'none'}.",
        f"Unexpected extras: {len(r.get('starter_unexpected_unlisted_members', []))} in starter manifest; {len(r.get('full_subset_unexpected_unlisted_members', []))} in full manifest.",
        f"External/embedded full checksum copies byte-identical: {r.get('full_checksum_copies', {}).get('byte_identical', False)}.",
        f"Full-manifest members outside this starter: {r.get('full_manifest_files_not_in_starter', 'unavailable')} (not a complete-export verification).", "",
        "## Essential low-speed inputs", "",
        *[f"- {'Present' if present else 'MISSING'}: `{name}`" for name, present in r.get('essential_file_presence', {}).items()], "",
        f"Double-clean drag model present: {r.get('dc_drag_model_present', False)}. Its absence is recorded, not treated as corruption; the submitted documentation reports a failed release gate.", "",
        "## Limits", "", r.get('checksum_coverage_note', ''), "",
        "Matching submitted checksums establishes internal byte consistency, not authenticated provenance or scientific correctness. Nested archives remain unopened. Geometry-to-member resolution, code reproducibility, and scientific numerical reconciliation require separate review.",
        "The starter does not include the full export's transonic source PDFs/evidence, network-port development folder, site repository, bulk historical run logs, or session transcript.", "",
        f"Extracted: {r['extracted']}. Payload: `{r.get('payload_directory', 'none')}`.",
        f"Post-extraction matching hashes: {r.get('post_extraction_matching_hashes', 0)}.",
        r.get('extraction_permissions', ''), "", r['scope'], "",
    ])


def self_test():
    for bad in ("/etc/passwd", "../x", f"{STARTER}/../x", f"{STARTER}//x", "C:/x", f"{STARTER}/x\\y", f"{STARTER}/./x"):
        try:
            safe_name(bad, STARTER)
        except ValueError:
            continue
        raise AssertionError(f"Accepted unsafe test path: {bad}")
    for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK):
        info = zipfile.ZipInfo(f"{STARTER}/test")
        info.external_attr = (kind | 0o777) << 16
        try:
            inspect_member(info)
        except ValueError:
            continue
        raise AssertionError(f"Accepted unsafe test mode: {kind}")
    print("Safety self-test passed: traversal/absolute/ambiguous paths, links, and special modes rejected.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--full-checksums", type=Path)
    parser.add_argument("--full-checksums-copy", type=Path)
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        if not args.archive:
            return
    if not args.archive or not args.full_checksums:
        parser.error("--archive and --full-checksums are required")
    result = verify(args.archive.resolve(), args.full_checksums.resolve(), args.full_checksums_copy, args.extract)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = OUT / f"verification_{stamp}.json"
    md_path = OUT / f"verification_{stamp}.md"
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    with md_path.open("x", encoding="utf-8") as stream:
        stream.write(report_text(result))
    print(json.dumps({"status": result["status"], "report_json": str(json_path), "report_markdown": str(md_path), "payload_directory": result.get("payload_directory")}, indent=2))
    if not result["status"].startswith("PASS"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
