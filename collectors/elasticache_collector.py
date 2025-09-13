# collectors/elasticache_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_elasticache_data():
    """
    Fetches detailed information about ElastiCache clusters (Redis and Memcached).
    Includes error handling for missing IAM permissions.
    """
    try:
        elasticache_client = boto3.client('elasticache')
        clusters_data = []
        
        # 1. Get Redis Replication Groups
        paginator_redis = elasticache_client.get_paginator('describe_replication_groups')
        for page in paginator_redis.paginate():
            for group in page.get('ReplicationGroups', []):
                primary_endpoint = group.get('NodeGroups', [{}])[0].get('PrimaryEndpoint', {})
                endpoint_address = primary_endpoint.get('Address', 'N/A')
                
                clusters_data.append({
                    'Name': group['ReplicationGroupId'],
                    'Engine': 'redis',
                    'NodeType': group['CacheNodeType'],
                    'Status': group['Status'],
                    'Endpoint': endpoint_address,
                    'Environment': get_environment_from_name(group['ReplicationGroupId'])
                })
        
        # 2. Get all cache clusters and find the standalone Memcached ones
        paginator_mc = elasticache_client.get_paginator('describe_cache_clusters')
        for page in paginator_mc.paginate(ShowCacheNodeInfo=True):
            for cluster in page.get('CacheClusters', []):
                # We only care about clusters that are NOT part of a Redis replication group
                if cluster['Engine'] == 'memcached':
                    endpoint = cluster.get('ConfigurationEndpoint', {})
                    endpoint_address = endpoint.get('Address', 'N/A')
                    
                    clusters_data.append({
                        'Name': cluster['CacheClusterId'],
                        'Engine': 'memcached',
                        'NodeType': cluster['CacheNodeType'],
                        'Status': cluster['CacheClusterStatus'],
                        'Endpoint': endpoint_address,
                        'Environment': get_environment_from_name(cluster['CacheClusterId'])
                    })

        return {'clusters': clusters_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for ElastiCache services. Skipping ElastiCache data collection.")
            return {'error': '(NO IAM ACCESS)', 'clusters': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_elasticache_data: {e}")
            raise e