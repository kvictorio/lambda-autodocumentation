# collectors/dynamodb_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_dynamodb_data():
    """
    Fetches detailed information about DynamoDB tables.
    Includes error handling for missing IAM permissions.
    """
    try:
        dynamodb_client = boto3.client('dynamodb')
        tables_data = []
        
        paginator = dynamodb_client.get_paginator('list_tables')
        for page in paginator.paginate():
            for table_name in page.get('TableNames', []):
                details = dynamodb_client.describe_table(TableName=table_name).get('Table', {})
                
                # Format the primary key schema
                key_schema = []
                for key in details.get('KeySchema', []):
                    key_type = "HASH" if key['KeyType'] == 'HASH' else "RANGE"
                    key_schema.append(f"{key['AttributeName']} ({key_type})")

                # Determine billing mode
                billing_mode = "PROVISIONED"
                if 'BillingModeSummary' in details and details['BillingModeSummary']['BillingMode'] == 'PAY_PER_REQUEST':
                    billing_mode = "On-Demand"
                
                tables_data.append({
                    'Name': table_name,
                    'Status': details.get('TableStatus'),
                    'ItemCount': details.get('ItemCount', 0),
                    'TableSizeMB': round(details.get('TableSizeBytes', 0) / (1024 * 1024), 2),
                    'PrimaryKey': ", ".join(key_schema),
                    'BillingMode': billing_mode,
                    'Environment': get_environment_from_name(table_name)
                })
        
        return {'tables': tables_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for DynamoDB services. Skipping DynamoDB data collection.")
            return {'error': '(NO IAM ACCESS)', 'tables': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_dynamodb_data: {e}")
            raise e