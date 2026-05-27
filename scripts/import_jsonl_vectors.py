#!/usr/bin/env python3
"""
JSONL Vector Import Script

Imports pre-computed Qdrant vectors from JSONL files into the knowledge base.
Each JSONL line should contain a complete Qdrant point with vector and payload.

Usage:
    python scripts/import_jsonl_vectors.py \\
        --file data/vectors.jsonl \\
        --org-id ORG_UUID \\
        --user-id USER_UUID \\
        --dry-run --verbose
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import ValidationError, validate  # type: ignore[import-untyped]
from qdrant_client import QdrantClient, models


def uuid7():
    """
    Generate a proper sequential UUIDv7 (per RFC 9562).
    Monotonically increasing, lexicographically sortable.
    """
    import os
    import time
    import uuid

    # 1. Unix timestamp in milliseconds (48 bits)
    unix_ts_ms = int(time.time() * 1000)

    # 2. Random 80 bits for the remaining fields
    rand = bytearray(os.urandom(10))

    # 3. Build UUID components

    # Timestamp high (32 bits) and low (16 bits)
    time_high = unix_ts_ms >> 16
    time_low = unix_ts_ms & 0xFFFF

    # Set version (UUIDv7 = 0b0111 = 0x7)
    rand[0] = (rand[0] & 0x0F) | 0x70  # top 4 bits replaced with version 7

    # Set variant (RFC 4122 = 0b10xx)
    rand[2] = (rand[2] & 0x3F) | 0x80

    # 4. Assemble the final 128-bit UUID
    uuid_bytes = time_high.to_bytes(4, "big") + time_low.to_bytes(2, "big") + bytes(rand)

    return uuid.UUID(bytes=uuid_bytes)


# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load JSON schema from file."""
    with open(schema_path, "r") as f:
        return json.load(f)


def map_jsonl_to_payload(
    jsonl_obj: Dict[str, Any], org_id: str, user_id: str, original_id: str, project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Map user's JSONL object to FileChunk payload format.

    Input schema:
        {
          "id": "...",
          "vector": [...],
          "payload": {
            "text": "...",
            "startPosition": 123,
            "endPosition": 456,
            "chunkIndex": 0,
            "fileId": "...",
            "fileName": "...",
            "embeddingModel": "...",
            "metadata": {"source": "...", "section": "...", "chunk_index": 0}
          }
        }

    Output schema: FileChunk (see scripts/schemas/file_chunk_schema.json)
    """
    payload = jsonl_obj.get("payload", {})
    user_metadata = payload.get("metadata", {})

    # Extract file_id from JSONL (not CLI)
    file_id = str(payload.get("fileId", ""))
    if not file_id:
        raise ValueError("Missing 'payload.fileId' in JSONL object")

    # Build required meta_data fields
    meta_data: Dict[str, Any] = {
        # Required fields
        "page": user_metadata.get("chunk_index", payload.get("chunkIndex", 0)),
        "chunk": payload.get("chunkIndex", 0),
        "chunk_size": len(payload.get("text", "")),
        "org_id": org_id,
        "project_id": project_id,
        "file_id": file_id,
        "original_filename": payload.get("fileName", "unknown"),
        "file_type": "imported",
        "content_type": "application/jsonl",
        "source_id": file_id,  # Same as file_id
        "user_id": user_id,
        "file_hash": hashlib.md5(file_id.encode()).hexdigest(),
        "file_size": payload.get("endPosition", 0),
        "source_point_id": original_id,
    }

    # Preserve additional fields from user's payload
    if "embeddingModel" in payload:
        meta_data["embedding_model"] = payload["embeddingModel"]
    if "startPosition" in payload:
        meta_data["start_position"] = payload["startPosition"]
    if "endPosition" in payload:
        meta_data["end_position"] = payload["endPosition"]

    # Merge any extra metadata from user (source, section, etc.)
    for key, value in user_metadata.items():
        if key not in meta_data:  # Don't override required fields
            meta_data[key] = value

    # Construct FileChunk payload
    chunk_payload = {
        "name": payload.get("fileName", "unknown"),
        "meta_data": meta_data,
        "content": payload.get("text", ""),
        "usage": None,
    }

    return chunk_payload


def validate_payload(payload: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validate payload against JSON schema."""
    try:
        validate(instance=payload, schema=schema)
        return True
    except ValidationError as e:
        logger.error(f"Schema validation failed: {e.message}")
        return False


def process_jsonl_file(
    file_path: Path, org_id: str, user_id: str, project_id: Optional[str], schema: Dict[str, Any], verbose: bool = False
) -> tuple[List[models.PointStruct], List[Dict[str, Any]]]:
    """
    Process JSONL file and return Qdrant points.

    Returns:
        (valid_points, invalid_objects)
    """
    valid_points = []
    invalid_objects = []

    logger.info(f"Processing JSONL file: {file_path}")

    with open(file_path, "r") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                # Parse JSONL line
                jsonl_obj = json.loads(line)

                # Extract vector and id
                vector = jsonl_obj.get("vector")
                original_id = jsonl_obj.get("id", f"point_{line_num}")

                if not vector:
                    raise ValueError("Missing 'vector' field")

                # Map to FileChunk payload
                payload = map_jsonl_to_payload(
                    jsonl_obj, org_id=org_id, user_id=user_id, project_id=project_id, original_id=original_id
                )

                # Validate against schema
                if not validate_payload(payload, schema):
                    invalid_objects.append({"line": line_num, "id": original_id, "error": "Schema validation failed"})
                    continue

                # Create Qdrant point
                new_id = str(uuid7())
                point = models.PointStruct(id=new_id, vector=vector, payload=payload)

                valid_points.append(point)

                # Verbose output
                if verbose and len(valid_points) <= 3:
                    logger.info(f"\n--- Sample Point {len(valid_points)} (line {line_num}) ---")
                    logger.info(f"Original ID: {original_id}")
                    logger.info(f"New UUID ID: {new_id}")
                    logger.info(f"Vector dimensions: {len(vector)}")
                    logger.info(f"Payload:\n{json.dumps(payload, indent=2)}")

            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: Invalid JSON - {e}")
                invalid_objects.append({"line": line_num, "error": f"JSON parse error: {e}"})
            except Exception as e:
                logger.error(f"Line {line_num}: {e}")
                invalid_objects.append({"line": line_num, "error": str(e)})

    return valid_points, invalid_objects


def insert_to_qdrant(
    points: List[models.PointStruct],
    qdrant_url: str,
    qdrant_port: int,
    collection_name: str,
    batch_size: int = 100,
    qdrant_api_key: Optional[str] = None,
) -> bool:
    """Insert points to Qdrant in batches."""
    try:
        # Initialize client with optional API key
        client_params: dict[str, Any] = {"url": qdrant_url, "port": qdrant_port}
        if qdrant_api_key:
            client_params["api_key"] = qdrant_api_key
        client = QdrantClient(**client_params)

        # Check if collection exists
        try:
            client.get_collection(collection_name)
            logger.info(f"Using existing collection: {collection_name}")
        except Exception:
            logger.error(f"Collection '{collection_name}' does not exist")
            return False

        # Batch insert
        total_batches = (len(points) + batch_size - 1) // batch_size

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            client.upsert(collection_name=collection_name, wait=True, points=batch)

            logger.info(f"Inserted batch {batch_num}/{total_batches}: {len(batch)} points")

        logger.info(f"Successfully inserted {len(points)} points to '{collection_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to insert to Qdrant: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Import pre-computed JSONL vectors to Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument("--file", type=Path, required=True, help="Path to input JSONL file")
    parser.add_argument("--org-id", type=str, required=True, help="Organization UUID")
    parser.add_argument("--user-id", type=str, required=True, help="User UUID")

    # Optional arguments
    parser.add_argument("--project-id", type=str, default=None, help="Project UUID (optional, nullable)")
    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="http://localhost:6333",
        help="Qdrant server URL (default: http://localhost:6333)",
    )
    parser.add_argument("--qdrant-port", type=int, default=443, help="Qdrant server port (default: 443)")
    parser.add_argument(
        "--collection",
        type=str,
        default="unified_knowledge",
        help="Qdrant collection name (default: unified_knowledge)",
    )
    parser.add_argument(
        "--qdrant-api-key", type=str, default=None, help="Qdrant API key (optional, for cloud/authenticated instances)"
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for insertion (default: 100)")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not insert to Qdrant")
    parser.add_argument("--verbose", action="store_true", help="Print constructed objects (first 3 samples)")

    args = parser.parse_args()

    # Validate file exists
    if not args.file.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    # Load schema
    schema_path = Path(__file__).parent / "schemas" / "file_chunk_schema.json"
    if not schema_path.exists():
        logger.error(f"Schema file not found: {schema_path}")
        sys.exit(1)

    schema = load_schema(schema_path)
    logger.info(f"Loaded schema: {schema_path}")

    # Process JSONL
    valid_points, invalid_objects = process_jsonl_file(
        file_path=args.file,
        org_id=args.org_id,
        user_id=args.user_id,
        project_id=args.project_id,
        schema=schema,
        verbose=args.verbose,
    )

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total lines processed: {len(valid_points) + len(invalid_objects)}")
    logger.info(f"Valid points: {len(valid_points)}")
    logger.info(f"Invalid objects: {len(invalid_objects)}")

    if invalid_objects:
        logger.warning("\nInvalid objects:")
        for obj in invalid_objects[:10]:  # Show first 10
            logger.warning(f"  Line {obj.get('line')}: {obj.get('error')}")
        if len(invalid_objects) > 10:
            logger.warning(f"  ... and {len(invalid_objects) - 10} more")

    if valid_points and args.verbose:
        logger.info(f"\nVector dimensions: {len(valid_points[0].vector)}")  # type: ignore[arg-type]

    # Dry run mode
    if args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("DRY RUN MODE - No insertion performed")
        logger.info("=" * 60)
        return

    # Insert to Qdrant
    if valid_points:
        logger.info("\n" + "=" * 60)
        logger.info("INSERTING TO QDRANT")
        logger.info("=" * 60)
        success = insert_to_qdrant(
            points=valid_points,
            qdrant_url=args.qdrant_url,
            qdrant_port=args.qdrant_port,
            collection_name=args.collection,
            batch_size=args.batch_size,
            qdrant_api_key=args.qdrant_api_key,
        )

        if success:
            logger.info("\n✓ Import completed successfully!")
        else:
            logger.error("\n✗ Import failed")
            sys.exit(1)
    else:
        logger.warning("No valid points to insert")


if __name__ == "__main__":
    main()
