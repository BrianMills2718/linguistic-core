#!/usr/bin/env python3
"""Selectively acquire preregistered Yareta v2 files via archive HTTP ranges.

The Yareta public archive endpoint supports byte ranges and serves a standard
ZIP container. This tool reads only the ZIP directory plus the compressed
payload ranges for files already frozen in acquisition_manifest_v2.json.

No unrelated archive payload is downloaded.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import http.cookiejar
import json
import os
import struct
import urllib.request
import zlib
from pathlib import Path
from typing import Any

ARCHIVE_ID = "e72b9ec2-d097-45ac-8126-d04035407f51"
BASE_URL = f"https://access.yareta.unige.ch/access/metadata/{ARCHIVE_ID}"
TAIL_BYTES = 65536


def canonical_selection_hash(rows: list[dict[str, Any]]) -> str:
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class ArchiveRangeClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.base_url = base_url
        self._token_ready = False

    def _request(self, url: str, start: int | None = None, end: int | None = None):
        req = urllib.request.Request(
            url, headers={"User-Agent": "linguistic-core-grounding-probe/1"}
        )
        if start is not None:
            req.add_header("Range", f"bytes={start}-{end}")
        return req

    def ensure_token(self) -> None:
        if self._token_ready:
            return
        with self.opener.open(
            self._request(self.base_url + "/download-token"), timeout=60
        ) as response:
            if response.status != 200:
                raise RuntimeError(f"archive download-token returned {response.status}")
            response.read()
        self._token_ready = True

    def get_range(self, start: int, end: int) -> bytes:
        self.ensure_token()
        with self.opener.open(
            self._request(self.base_url + "/download", start, end), timeout=120
        ) as response:
            if response.status != 206:
                raise RuntimeError(
                    f"archive range {start}-{end} returned {response.status}, expected 206"
                )
            data = response.read()
            expected = end - start + 1
            if len(data) != expected:
                raise RuntimeError(
                    f"short range read {start}-{end}: {len(data)} != {expected}"
                )
            return data

    def archive_size(self) -> int:
        self.ensure_token()
        req = self._request(self.base_url + "/download", 0, 0)
        with self.opener.open(req, timeout=60) as response:
            if response.status != 206:
                raise RuntimeError(
                    f"archive size probe returned {response.status}, expected 206"
                )
            content_range = response.headers.get("Content-Range")
            response.read()
        if not content_range or "/" not in content_range:
            raise RuntimeError("archive size probe missing Content-Range")
        return int(content_range.rsplit("/", 1)[1])


def parse_eocd(tail: bytes, tail_absolute_start: int) -> dict[str, int]:
    index = tail.rfind(b"PK\x05\x06")
    if index < 0:
        raise ValueError("ZIP EOCD signature not found")
    if index + 22 > len(tail):
        raise ValueError("truncated ZIP EOCD")
    (
        signature,
        disk_number,
        central_disk,
        entries_on_disk,
        total_entries,
        central_size,
        central_offset,
        comment_length,
    ) = struct.unpack("<4s4H2LH", tail[index : index + 22])
    if disk_number or central_disk or entries_on_disk != total_entries:
        raise ValueError("multi-disk ZIP archives are unsupported")
    if comment_length != len(tail) - (index + 22):
        # The tail may start inside the archive; comment bytes, if any, must still
        # exactly follow the EOCD in the returned suffix.
        if index + 22 + comment_length > len(tail):
            raise ValueError("truncated ZIP comment")
    return {
        "eocd_absolute_offset": tail_absolute_start + index,
        "total_entries": total_entries,
        "central_size": central_size,
        "central_offset": central_offset,
        "comment_length": comment_length,
    }


def parse_central_directory(data: bytes) -> dict[str, dict[str, int]]:
    entries: dict[str, dict[str, int]] = {}
    offset = 0
    while offset < len(data):
        if data[offset : offset + 4] != b"PK\x01\x02":
            raise ValueError(f"invalid central-directory signature at byte {offset}")
        values = struct.unpack("<4s6H3L5H2L", data[offset : offset + 46])
        (
            _signature,
            _version_made,
            _version_needed,
            flags,
            method,
            _mtime,
            _mdate,
            crc32,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
            comment_length,
            _disk_start,
            _internal_attr,
            _external_attr,
            local_header_offset,
        ) = values
        name_bytes = data[offset + 46 : offset + 46 + name_length]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        name = name_bytes.decode(encoding)
        entries[name] = {
            "flags": flags,
            "method": method,
            "crc32": crc32,
            "compressed_size": compressed_size,
            "uncompressed_size": uncompressed_size,
            "local_header_offset": local_header_offset,
        }
        offset += 46 + name_length + extra_length + comment_length
    return entries


def select_manifest_entries(
    manifest: dict[str, Any], archive_entries: dict[str, dict[str, int]]
) -> list[tuple[str, dict[str, Any], dict[str, int]]]:
    rows = manifest["files"]
    expected_hash = manifest["selection_sha256"]
    actual_hash = canonical_selection_hash(rows)
    if actual_hash != expected_hash:
        raise ValueError(
            f"manifest selection hash mismatch: {actual_hash} != {expected_hash}"
        )

    selected: list[tuple[str, dict[str, Any], dict[str, int]]] = []
    for row in rows:
        archive_name = "researchdata" + row["full_name"]
        entry = archive_entries.get(archive_name)
        if entry is None:
            raise ValueError(f"selected file missing from ZIP: {archive_name}")
        if entry["uncompressed_size"] != row["size"]:
            raise ValueError(
                f"uncompressed size mismatch for {archive_name}: "
                f"{entry['uncompressed_size']} != {row['size']}"
            )
        if entry["method"] != 8:
            raise ValueError(
                f"unsupported compression method {entry['method']} for {archive_name}"
            )
        selected.append((archive_name, row, entry))
    return selected


def local_data_range(
    client: ArchiveRangeClient, archive_name: str, entry: dict[str, int]
) -> tuple[int, int]:
    offset = entry["local_header_offset"]
    header = client.get_range(offset, offset + 29)
    if header[:4] != b"PK\x03\x04":
        raise ValueError(f"invalid local header for {archive_name}")
    (
        _sig,
        _version_needed,
        _flags,
        method,
        _mtime,
        _mdate,
        _crc,
        _compressed_size,
        _uncompressed_size,
        name_length,
        extra_length,
    ) = struct.unpack("<4s5H3L2H", header)
    if method != entry["method"]:
        raise ValueError(f"compression-method drift for {archive_name}")
    data_start = offset + 30 + name_length + extra_length
    return data_start, data_start + entry["compressed_size"] - 1


def extract_one(
    client: ArchiveRangeClient,
    archive_name: str,
    row: dict[str, Any],
    entry: dict[str, int],
    output_root: Path,
) -> int:
    destination = output_root / row["full_name"].lstrip("/").replace("/", os.sep)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (
        destination.exists()
        and destination.stat().st_size == row["size"]
        and sha256_file(destination) == row["sha256"]
    ):
        return 0

    start, end = local_data_range(client, archive_name, entry)
    compressed = client.get_range(start, end)
    raw = zlib.decompress(compressed, -zlib.MAX_WBITS)
    if len(raw) != entry["uncompressed_size"]:
        raise ValueError(f"uncompressed-size mismatch for {archive_name}")
    if (binascii.crc32(raw) & 0xFFFFFFFF) != entry["crc32"]:
        raise ValueError(f"CRC32 mismatch for {archive_name}")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != row["sha256"]:
        raise ValueError(
            f"SHA256 mismatch for {archive_name}: {digest} != {row['sha256']}"
        )

    temporary = destination.with_suffix(destination.suffix + ".download")
    temporary.write_bytes(raw)
    temporary.replace(destination)
    return len(compressed)


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, default=here / "acquisition_manifest_v2.json"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=here / ".cache" / "yareta_v2_selected"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    client = ArchiveRangeClient()
    archive_size = client.archive_size()
    tail_size = min(TAIL_BYTES, archive_size)
    tail_start = archive_size - tail_size
    tail = client.get_range(tail_start, archive_size - 1)
    eocd = parse_eocd(tail, tail_start)
    central = client.get_range(
        eocd["central_offset"],
        eocd["central_offset"] + eocd["central_size"] - 1,
    )
    archive_entries = parse_central_directory(central)
    if len(archive_entries) != eocd["total_entries"]:
        raise ValueError(
            f"central-directory count {len(archive_entries)} != "
            f"EOCD count {eocd['total_entries']}"
        )
    selected = select_manifest_entries(manifest, archive_entries)

    compressed_total = sum(entry["compressed_size"] for _, _, entry in selected)
    print(
        f"archive={archive_size} bytes entries={len(archive_entries)} "
        f"selected={len(selected)} compressed_selected={compressed_total}"
    )
    if args.dry_run:
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    transferred = 0
    for index, (archive_name, row, entry) in enumerate(
        sorted(selected, key=lambda value: value[0]), 1
    ):
        transferred += extract_one(
            client, archive_name, row, entry, args.output_dir
        )
        if index % 20 == 0 or index == len(selected):
            print(
                f"verified {index}/{len(selected)} "
                f"compressed_payload_transferred={transferred}"
            )
    print(
        f"done files={len(selected)} "
        f"compressed_payload_transferred={transferred}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
