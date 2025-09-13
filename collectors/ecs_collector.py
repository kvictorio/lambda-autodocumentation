# collectors/ecs_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_container_data():
    """
    Fetches detailed information about ECR, EKS, and ECS resources.
    Includes error handling for missing IAM permissions.
    """
    try:
        ecr_client = boto3.client('ecr')
        eks_client = boto3.client('eks')
        ecs_client = boto3.client('ecs')
        
        ecr_repos = []
        eks_clusters = []
        ecs_clusters = []

        # 1. Get ECR Repositories
        paginator_ecr = ecr_client.get_paginator('describe_repositories')
        for page in paginator_ecr.paginate():
            for repo in page.get('repositories', []):
                ecr_repos.append({
                    'Name': repo['repositoryName'],
                    'URI': repo['repositoryUri'],
                    'Environment': get_environment_from_name(repo['repositoryName'])
                })

        # 2. Get EKS Clusters
        cluster_names = eks_client.list_clusters().get('clusters', [])
        for name in cluster_names:
            cluster_details = eks_client.describe_cluster(name=name).get('cluster', {})
            eks_clusters.append({
                'Name': name,
                'Version': cluster_details.get('version'),
                'Status': cluster_details.get('status'),
                'Environment': get_environment_from_name(name)
            })

        # 3. Get ECS Clusters and their Services
        cluster_arns = ecs_client.list_clusters().get('clusterArns', [])
        if cluster_arns:
            described_clusters = ecs_client.describe_clusters(clusters=cluster_arns).get('clusters', [])
            for cluster in described_clusters:
                cluster_name = cluster['clusterName']
                
                # Get services within the cluster
                services_data = []
                paginator_ecs_services = ecs_client.get_paginator('list_services')
                for page in paginator_ecs_services.paginate(cluster=cluster_name):
                    service_arns = page.get('serviceArns', [])
                    if service_arns:
                        described_services = ecs_client.describe_services(cluster=cluster_name, services=service_arns).get('services', [])
                        for service in described_services:
                            services_data.append({
                                'Name': service['serviceName'],
                                'Status': service['status'],
                                'LaunchType': service.get('launchType', 'N/A'),
                                'DesiredCount': service.get('desiredCount')
                            })

                ecs_clusters.append({
                    'Name': cluster_name,
                    'Status': cluster['status'],
                    'Services': services_data,
                    'Environment': get_environment_from_name(cluster_name)
                })

        return {
            'ecr_repositories': ecr_repos,
            'eks_clusters': eks_clusters,
            'ecs_clusters': ecs_clusters
        }
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Container services (ECS/EKS/ECR). Skipping.")
            return {'error': '(NO IAM ACCESS)', 'ecr_repositories': [], 'eks_clusters': [], 'ecs_clusters': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_container_data: {e}")
            raise e