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
from reporting.markdown_report import generate_text_report
from reporting.mermaid_diagram import generate_mermaid_diagram
from collectors.vpc_collector import get_vpc_data


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

    # 1. Fetch data from all services
    ec2_resources = get_ec2_data()
    lambda_resources = get_lambda_data()
    s3_resources = get_s3_data()
    apigateway_resources = get_apigateway_data()
    vpc_resources = get_vpc_data()
    
    # 2. Consolidate and categorize all resources
    categorized_data = {}
    all_resources_list = [
        ('instances', ec2_resources['instances']),
        ('security_groups', ec2_resources['security_groups']),
        ('functions', lambda_resources['functions']),
        ('s3_buckets', s3_resources['buckets']),
        ('api_gateways', apigateway_resources['apis']),
        ('vpcs', vpc_resources['vpcs'])
    ]

    for category_name, resource_list in all_resources_list:
        for resource in resource_list:
            env = resource['Environment']
            if env not in categorized_data: categorized_data[env] = {}
            if category_name not in categorized_data[env]: categorized_data[env][category_name] = []
            categorized_data[env][category_name].append(resource)

    # 3. Generate and upload reports
    main_readme_content = [f"# AWS Infrastructure Report", f"_Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}_", "\n## Discovered Environments\n"]
    
    for env_name, env_data in sorted(categorized_data.items()):
        print(f"Generating documents for environment: {env_name}")
        main_readme_content.append(f"* [{env_name.upper()}](./{env_name}-documentation.md)")

        report_content = generate_text_report(env_name, env_data)
        diagram_content = generate_mermaid_diagram(env_name, env_data, ec2_resources['security_groups'])

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