import boto3
import fnmatch
from helpers.data_backend.base import BaseDataBackend

class S3DataBackend(BaseDataBackend):
    def __init__(
        self,
        bucket_name,
        region_name="us-east-1",
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
    ):
        self.bucket_name = bucket_name
        self.client = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def read(self, s3_key):
        """Retrieve and return the content of the file from S3."""
        response = self.client.get_object(Bucket=self.bucket_name, Key=s3_key)
        return response["Body"].read()

    def write(self, s3_key, data):
        """Upload data to the specified S3 key."""
        self.client.put_object(Body=data, Bucket=self.bucket_name, Key=s3_key)

    def delete(self, s3_key):
        """Delete the specified file from S3."""
        self.client.delete_object(Bucket=self.bucket_name, Key=s3_key)

    def list_by_prefix(self, prefix=""):
        """List all files under a specific path (prefix) in the S3 bucket."""
        response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        return [item["Key"] for item in response.get("Contents", [])]

    def list_files(self, str_pattern: str, instance_data_root = None):
        files = self.list_by_prefix()  # List all files
        return [file for file in files if fnmatch.fnmatch(file, str_pattern)]