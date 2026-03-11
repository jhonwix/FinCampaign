"""
Document upload and indexing for Vertex AI Search.

Two-step process:
1. Upload local TXT files to GCS (Discovery Engine imports from GCS URIs).
2. Trigger a Discovery Engine ImportDocuments operation.
"""

from pathlib import Path

from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage as gcs_storage
from google.oauth2 import service_account

from config import settings


def _credentials():
    return service_account.Credentials.from_service_account_file(
        settings.service_account_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def upload_to_gcs(local_path: str, gcs_prefix: str = "rag-documents") -> str:
    """
    Upload a local file to GCS for staging.

    Returns:
        GCS URI, e.g. gs://bucket/rag-documents/file.txt
    """
    client = gcs_storage.Client(
        project=settings.google_cloud_project,
        credentials=_credentials(),
    )
    bucket = client.bucket(settings.gcs_bucket_name)

    filename = Path(local_path).name
    blob_name = f"{gcs_prefix}/{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path, content_type="text/plain")

    gcs_uri = f"gs://{settings.gcs_bucket_name}/{blob_name}"
    print(f"[Indexer] Uploaded {filename} -> {gcs_uri}")
    return gcs_uri


def import_documents_from_gcs(
    gcs_uris: list[str],
    datastore_id: str | None = None,
) -> dict:
    """
    Import documents into Vertex AI Search from GCS URIs.
    Blocks until the import operation completes (use in scripts, not API).

    Args:
        gcs_uris: List of GCS URIs. Wildcards supported (*.txt).
        datastore_id: Target datastore (settings default if None).

    Returns:
        Dict with 'operation' name and 'error_count'.
    """
    datastore_id = datastore_id or settings.vertex_ai_datastore_id
    client = discoveryengine.DocumentServiceClient(credentials=_credentials())

    parent = (
        f"projects/{settings.google_cloud_project}"
        f"/locations/global/collections/default_collection"
        f"/dataStores/{datastore_id}/branches/default_branch"
    )

    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=discoveryengine.GcsSource(
            input_uris=gcs_uris,
            data_schema="content",
        ),
        reconciliation_mode=(
            discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL
        ),
    )

    operation = client.import_documents(request=request)
    print(f"[Indexer] Import operation: {operation.operation.name}")

    response = operation.result(timeout=600)
    error_count = len(response.error_samples)
    print(f"[Indexer] Import complete. Errors: {error_count}")

    return {
        "operation": operation.operation.name,
        "error_count": error_count,
    }


def index_local_documents(documents_dir: str) -> dict:
    """
    Convenience wrapper: upload all .txt files from a directory and index them.

    Args:
        documents_dir: Path to directory containing .txt files.

    Returns:
        Summary dict including 'files_uploaded', 'operation', 'error_count'.
    """
    txt_files = list(Path(documents_dir).glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {documents_dir}")

    gcs_uris = [upload_to_gcs(str(f)) for f in txt_files]
    result = import_documents_from_gcs(gcs_uris)
    result["files_uploaded"] = [f.name for f in txt_files]
    return result
