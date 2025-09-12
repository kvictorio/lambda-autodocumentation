# collectors/s3_collector.py
import boto3
from utils import get_environment_from_name

def get_s3_data():
    s3_client = boto3.client('s3')
    buckets_data = []
    response = s3_client.list_buckets()
    for bucket in response['Buckets']:
        bucket_name = bucket['Name']
        tags = []
        try:
            tag_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = tag_response.get('TagSet', [])
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                print(f"Could not get tags for bucket {bucket_name}: {e}")
        
        buckets_data.append({
            'Name': bucket_name,
            'Environment': get_environment_from_name(bucket_name, tags)
        })
    return {'buckets': buckets_data}