"""
Vertex AI Search datastore management.
Used by scripts, not by the live API.
"""

from google.api_core.exceptions import AlreadyExists
from google.cloud import discoveryengine_v1 as discoveryengine
from google.oauth2 import service_account

from config import settings


def _credentials():
    return service_account.Credentials.from_service_account_file(
        settings.service_account_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def create_datastore(
    datastore_id: str | None = None,
    display_name: str = "FinCampaign RAG Datastore",
) -> dict:
    """
    Create a Vertex AI Search datastore for unstructured text documents.

    Returns:
        Dict with 'name' and 'state' keys.
    """
    datastore_id = datastore_id or settings.vertex_ai_datastore_id
    client = discoveryengine.DataStoreServiceClient(credentials=_credentials())

    parent = (
        f"projects/{settings.google_cloud_project}"
        f"/locations/global/collections/default_collection"
    )

    data_store = discoveryengine.DataStore(
        display_name=display_name,
        industry_vertical=discoveryengine.IndustryVertical.GENERIC,
        content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
        document_processing_config=discoveryengine.DocumentProcessingConfig(
            default_parsing_config=discoveryengine.DocumentProcessingConfig.ParsingConfig(
                digital_parsing_config=(
                    discoveryengine.DocumentProcessingConfig
                    .ParsingConfig.DigitalParsingConfig()
                )
            )
        ),
    )

    try:
        operation = client.create_data_store(
            request=discoveryengine.CreateDataStoreRequest(
                parent=parent,
                data_store=data_store,
                data_store_id=datastore_id,
            )
        )
        response = operation.result(timeout=300)
        return {"name": response.name, "state": "CREATED"}
    except AlreadyExists:
        return {
            "name": f"{parent}/dataStores/{datastore_id}",
            "state": "ALREADY_EXISTS",
        }


def get_datastore_info(datastore_id: str | None = None) -> dict:
    """Retrieve metadata for an existing datastore."""
    datastore_id = datastore_id or settings.vertex_ai_datastore_id
    client = discoveryengine.DataStoreServiceClient(credentials=_credentials())
    name = (
        f"projects/{settings.google_cloud_project}"
        f"/locations/global/collections/default_collection"
        f"/dataStores/{datastore_id}"
    )
    ds = client.get_data_store(name=name)
    return {
        "name": ds.name,
        "display_name": ds.display_name,
        "industry_vertical": str(ds.industry_vertical),
    }
