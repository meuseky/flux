import boto3
from flux.plugins import StoragePlugin
from flux.output_storage import OutputStorage, OutputStorageReference
from flux.config import Configuration

class S3Storage(OutputStorage):
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.bucket = Configuration.get().settings.storage.get("s3_bucket", "flux-bucket")

    def retrieve(self, reference: OutputStorageReference) -> Any:
        if reference.storage_type != "s3":
            raise ValueError(f"Invalid storage type: {reference.storage_type}")
        response = self.s3.get_object(Bucket=self.bucket, Key=reference.reference_id)
        return dill.loads(response["Body"].read())

    def store(self, reference_id: str, value: Any) -> OutputStorageReference:
        self.s3.put_object(Bucket=self.bucket, Key=reference_id, Body=dill.dumps(value))
        return OutputStorageReference(
            storage_type="s3",
            reference_id=reference_id,
            metadata={"bucket": self.bucket}
        )

    def delete(self, reference: OutputStorageReference) -> None:
        if reference.storage_type != "s3":
            raise ValueError(f"Invalid storage type: {reference.storage_type}")
        self.s3.delete_object(Bucket=self.bucket, Key=reference.reference_id)

class S3StoragePlugin(StoragePlugin):
    def __init__(self):
        super().__init__("s3", S3Storage)