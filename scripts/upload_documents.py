#!/usr/bin/env python3
"""
Upload and index RAG documents into Vertex AI Search.

Usage:
    python scripts/upload_documents.py
    python scripts/upload_documents.py --dir ./rag_documents
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import settings
from rag.indexer import index_local_documents


def main():
    parser = argparse.ArgumentParser(
        description="Upload RAG documents to Vertex AI Search"
    )
    parser.add_argument(
        "--dir",
        default=os.path.join(os.path.dirname(__file__), "..", "rag_documents"),
        help="Directory containing .txt files (default: ../rag_documents)",
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.dir)

    print("=" * 60)
    print("FinCampaign — Upload RAG Documents")
    print("=" * 60)
    print(f"Project:   {settings.google_cloud_project}")
    print(f"Datastore: {settings.vertex_ai_datastore_id}")
    print(f"GCS bucket: {settings.gcs_bucket_name}")
    print(f"Source dir: {docs_dir}")
    print()

    result = index_local_documents(docs_dir)

    print()
    print("Upload complete.")
    print(f"Files indexed: {result['files_uploaded']}")
    print(f"Operation:     {result.get('operation', 'N/A')}")
    print(f"Errors:        {result.get('error_count', 0)}")
    print()
    print("Note: Full indexing in Vertex AI Search may take 10–15 minutes.")
    print("Run the test pipeline after indexing is complete.")


if __name__ == "__main__":
    main()
