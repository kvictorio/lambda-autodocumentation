# collectors/rds_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_rds_data():
    """
    Fetches detailed information about RDS instances.
    Includes error handling for missing IAM permissions.
    """
    try:
        rds_client = boto3.client('rds')
        instances_data = []
        
        paginator = rds_client.get_paginator('describe_db_instances')
        for page in paginator.paginate():
            for instance in page['DBInstances']:
                endpoint = instance.get('Endpoint', {})
                
                subnet_ids = []
                if instance.get('DBSubnetGroup'):
                    subnets = instance['DBSubnetGroup'].get('Subnets', [])
                    subnet_ids = [s['SubnetIdentifier'] for s in subnets]
                
                sg_ids = [sg['VpcSecurityGroupId'] for sg in instance.get('VpcSecurityGroups', [])]

                instances_data.append({
                    'Name': instance['DBInstanceIdentifier'],
                    'Engine': f"{instance['Engine']} ({instance.get('EngineVersion')})",
                    'InstanceClass': instance['DBInstanceClass'],
                    'Status': instance['DBInstanceStatus'],
                    'Endpoint': f"{endpoint.get('Address', 'N/A')}:{endpoint.get('Port', 'N/A')}",
                    'DBClusterIdentifier': instance.get('DBClusterIdentifier', 'N/A (Standalone)'),
                    'SubnetIds': subnet_ids,
                    'SecurityGroupIds': sg_ids,
                    'Environment': get_environment_from_name(instance['DBInstanceIdentifier'], instance.get('TagList', []))
                })
        
        return {'instances': instances_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for RDS services. Skipping RDS data collection.")
            return {'error': '(NO IAM ACCESS)', 'instances': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_rds_data: {e}")
            raise e