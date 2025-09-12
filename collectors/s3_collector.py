# collectors/s3_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_s3_data():
    """
    Fetches information about S3 buckets.
    Includes error handling for missing IAM permissions.
    """
    try:
        s3_client = boto3.client('s3')
        buckets_data = []
        
        # This API call requires s3:ListAllMyBuckets permission
        response = s3_client.list_buckets()
        
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            tags = []
            try:
                # This API call requires s3:GetBucketTagging permission
                tag_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
                tags = tag_response.get('TagSet', [])
            except ClientError as e:
                # A "NoSuchTagSet" error is normal for buckets without tags, so we ignore it.
                # We only care if we are denied permission completely.
                if 'NoSuchTagSet' not in str(e) and 'AccessDenied' not in str(e):
                    print(f"Could not get tags for bucket {bucket_name}: {e}")
            
            buckets_data.append({
                'Name': bucket_name,
                'Environment': get_environment_from_name(bucket_name, tags)
            })
            
        return {'buckets': buckets_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for S3 services. Skipping S3 data collection.")
            return {'error': '(NO IAM ACCESS)', 'buckets': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_s3_data: {e}")
            raise e