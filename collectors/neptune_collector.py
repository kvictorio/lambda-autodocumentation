# collectors/neptune_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_neptune_data():
    """
    Fetches detailed information about Neptune DB clusters and instances.
    Includes error handling for missing IAM permissions.
    """
    try:
        neptune_client = boto3.client('neptune')
        clusters_data = []
        
        paginator = neptune_client.get_paginator('describe_db_clusters')
        for page in paginator.paginate():
            for cluster in page['DBClusters']:
                cluster_id = cluster['DBClusterIdentifier']
                
                # Get instances within the cluster
                instances_in_cluster = []
                for member in cluster.get('DBClusterMembers', []):
                    instance_id = member['DBInstanceIdentifier']
                    # Get full details for each instance
                    instance_details_response = neptune_client.describe_db_instances(DBInstanceIdentifier=instance_id)
                    if instance_details_response.get('DBInstances'):
                        instance = instance_details_response['DBInstances'][0]
                        endpoint = instance.get('Endpoint', {})
                        subnets = [s['SubnetIdentifier'] for s in instance.get('DBSubnetGroup', {}).get('Subnets', [])]
                        sgs = [sg['VpcSecurityGroupId'] for sg in instance.get('VpcSecurityGroups', [])]
                        
                        instances_in_cluster.append({
                            'Name': instance_id,
                            'InstanceClass': instance['DBInstanceClass'],
                            'Endpoint': f"{endpoint.get('Address', 'N/A')}:{endpoint.get('Port', 'N/A')}",
                            'SubnetIds': subnets,
                            'SecurityGroupIds': sgs,
                            'IsClusterWriter': member.get('IsClusterWriter', False)
                        })

                clusters_data.append({
                    'Name': cluster_id,
                    'Engine': f"{cluster['Engine']} ({cluster.get('EngineVersion')})",
                    'Status': cluster['Status'],
                    'Endpoint': cluster.get('Endpoint', 'N/A'),
                    'ReaderEndpoint': cluster.get('ReaderEndpoint', 'N/A'),
                    'Instances': instances_in_cluster,
                    'Environment': get_environment_from_name(cluster_id, cluster.get('TagList', []))
                })
        
        return {'clusters': clusters_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Neptune services. Skipping Neptune data collection.")
            return {'error': '(NO IAM ACCESS)', 'clusters': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_neptune_data: {e}")
            raise e