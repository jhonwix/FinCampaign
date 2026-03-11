#!/usr/bin/env python3
"""
Create the Vertex AI Search datastore for FinCampaign RAG.
Run this once before uploading documents.

Usage:
    python scripts/create_datastore.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import settings
from rag.datastore import create_datastore


def main():
    print("=" * 60)
    print("FinCampaign — Create Vertex AI Search Datastore")
    print("=" * 60)
    print(f"Project:   {settings.google_cloud_project}")
    print(f"Location:  global (Discovery Engine always uses global)")
    print(f"Datastore: {settings.vertex_ai_datastore_id}")
    print()

    result = create_datastore()

    if result["state"] == "ALREADY_EXISTS":
        print(f"Datastore already exists: {result['name']}")
    else:
        print(f"Datastore created: {result['name']}")

    print()
    print("Next step: python scripts/upload_documents.py")


if __name__ == "__main__":
    main()
