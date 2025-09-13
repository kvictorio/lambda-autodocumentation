# lambda_function.py
import os
import json
from datetime import datetime
import boto3

# Import our custom functions from the new modules
from collectors.ec2_collector import get_ec2_data
from collectors.lambda_collector import get_lambda_data
from collectors.s3_collector import get_s3_data
from collectors.apigateway_collector import get_apigateway_data
from collectors.vpc_collector import get_vpc_data
from collectors.rds_collector import get_rds_data
from collectors.cognito_collector import get_cognito_data
from collectors.ecs_collector import get_container_data
from collectors.neptune_collector import get_neptune_data
from collectors.dynamodb_collector import get_dynamodb_data
from collectors.elasticache_collector import get_elasticache_data
from collectors.queues_collector import get_queues_data
from reporting.markdown_report import generate_text_report
from reporting.mermaid_diagram import generate_mermaid_diagram

# Environment variable for the S3 bucket
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
if not S3_BUCKET_NAME:
    raise ValueError("S3_BUCKET_NAME environment variable not set.")

def upload_to_s3(content, bucket, object_name):
    """Uploads a string content to an S3 object."""
    s3_client = boto3.client('s3')
    try:
        s3_client.put_object(Body=content, Bucket=bucket, Key=object_name)
        print(f"Successfully uploaded {object_name} to {bucket}")
    except Exception as e:
        print(f"Error uploading file: {e}")
        raise e

def lambda_handler(event, context):
    """Main function executed by AWS Lambda."""
    print("Starting infrastructure documentation process...")
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d")

    # 1. Fetch data from all services into a single dictionary
    all_resources = {
        'ec2': get_ec2_data(),
        'lambda': get_lambda_data(),
        's3': get_s3_data(),
        'apigateway': get_apigateway_data(),
        'vpc': get_vpc_data(),
        'rds': get_rds_data(),
        'cognito': get_cognito_data(),
        'container': get_container_data(),
        'neptune': get_neptune_data(),
        'dynamodb': get_dynamodb_data(),
        'elasticache': get_elasticache_data(),
        'queues': get_queues_data() 
    }
    
    # 2. Consolidate and categorize all resources, safely getting lists
    categorized_data = {}
    resource_map = {
        'instances': all_resources['ec2'].get('instances', []),
        'security_groups': all_resources['ec2'].get('security_groups', []),
        'functions': all_resources['lambda'].get('functions', []),
        's3_buckets': all_resources['s3'].get('buckets', []),
        'api_gateways': all_resources['apigateway'].get('apis', []),
        'vpcs': all_resources['vpc'].get('vpcs', []),
        'rds_instances': all_resources['rds'].get('instances', []),
        'user_pools': all_resources['cognito'].get('user_pools', []),
        'ecr_repositories': all_resources['container'].get('ecr_repositories', []),
        'eks_clusters': all_resources['container'].get('eks_clusters', []),
        'ecs_clusters': all_resources['container'].get('ecs_clusters', []),
        'neptune_clusters': all_resources['neptune'].get('clusters', []),
        'dynamodb_tables': all_resources['dynamodb'].get('tables', []),
        'elasticache_clusters': all_resources['elasticache'].get('clusters', []),
        'sqs_queues': all_resources['queues'].get('sqs_queues', []),
        'kinesis_streams': all_resources['queues'].get('kinesis_streams', []),
        'firehose_streams': all_resources['queues'].get('firehose_streams', [])
    }

    for category_name, resource_list in resource_map.items():
        if not resource_list: # Skip if the list is empty (e.g., due to an error or no resources)
            continue
        for resource in resource_list:
            env = resource.get('Environment', 'no-category')
            if env not in categorized_data: categorized_data[env] = {}
            if category_name not in categorized_data[env]: categorized_data[env][category_name] = []
            categorized_data[env][category_name].append(resource)
    
    # Securitygroup cross reference
    sg_cross_reference = {}
    # Cross-reference EC2 instances
    for instance in all_resources['ec2'].get('instances', []):
        for sg_id in instance.get('SecurityGroups', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"EC2: {instance['Name']}")
    # Cross-reference RDS instances
    for rds in all_resources['rds'].get('instances', []):
        for sg_id in rds.get('SecurityGroupIds', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"RDS: {rds['Name']}")
    # Cross-reference Lambda functions
    for func in all_resources['lambda'].get('functions', []):
        for sg_id in func.get('SecurityGroupIds', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"Lambda: {func['Name']}")
    # Cross-reference Load Balancers
    for vpc in all_resources['vpc'].get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            for sg_id in lb.get('SecurityGroupIds', []):
                if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
                sg_cross_reference[sg_id].append(f"Load Balancer: {lb['Name']}")
            
    # 3. Generate and upload reports
    main_readme_content = [f"# AWS Infrastructure Report", f"_Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}_", "\n## Discovered Environments\n"]
    
    if not categorized_data:
        main_readme_content.append("\n_No resources were found..._")

    for env_name, env_data in sorted(categorized_data.items()):
        print(f"Generating documents for environment: {env_name}")
        main_readme_content.append(f"* [{env_name.upper()}](./{env_name}-documentation.md)")

        report_content = generate_text_report(env_name, env_data, all_resources, sg_cross_reference)
        
        diagram_content = generate_mermaid_diagram(env_name, env_data, all_resources)

        s3_report_key = f'reports/{timestamp}/{env_name}-documentation.md'
        s3_diagram_key = f'reports/{timestamp}/{env_name}-diagram.mmd'

        upload_to_s3(report_content, S3_BUCKET_NAME, s3_report_key)
        upload_to_s3(diagram_content, S3_BUCKET_NAME, s3_diagram_key)

    s3_readme_key = f'reports/{timestamp}/README.md'
    upload_to_s3("\n".join(main_readme_content), S3_BUCKET_NAME, s3_readme_key)

    print("Process completed successfully.")
    return {
        'statusCode': 200,
        'body': json.dumps(f'Documentation successfully generated and uploaded to s3://{S3_BUCKET_NAME}/reports/{timestamp}/')
    }