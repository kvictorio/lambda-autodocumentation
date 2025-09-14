import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_lambda_data():
    """
    Fetches detailed information about Lambda functions, including their VPC configuration,
    environment variables, and event source triggers.
    """
    try:
        lambda_client = boto3.client('lambda')
        functions_data = []
        event_source_mappings = [] # <-- ADDED
        
        # Get Function Details
        paginator = lambda_client.get_paginator('list_functions')
        for page in paginator.paginate():
            for function in page['Functions']:
                vpc_config = function.get('VpcConfig')
                
                function_details = {
                    'Name': function['FunctionName'],
                    'Runtime': function.get('Runtime', 'Container/Unknown'),
                    'Environment': get_environment_from_name(function['FunctionName']),
                    'EnvironmentVariables': function.get('Environment', {}).get('Variables', {}),
                    'VpcId': None,
                    'SubnetIds': [],
                    'SecurityGroupIds': []
                }

                if vpc_config and vpc_config.get('VpcId'):
                    function_details['VpcId'] = vpc_config.get('VpcId')
                    function_details['SubnetIds'] = vpc_config.get('SubnetIds', [])
                    function_details['SecurityGroupIds'] = vpc_config.get('SecurityGroupIds', [])
                
                functions_data.append(function_details)

        # Get Event Source Mappings (Triggers) <-- ADDED SECTION
        paginator_esm = lambda_client.get_paginator('list_event_source_mappings')
        for page in paginator_esm.paginate():
            for mapping in page.get('EventSourceMappings', []):
                event_source_mappings.append({
                    'FunctionArn': mapping['FunctionArn'],
                    'EventSourceArn': mapping['EventSourceArn']
                })
                
        return {
            'functions': functions_data,
            'event_source_mappings': event_source_mappings # <-- ADDED
        }
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Lambda services. Skipping Lambda data collection.")
            return {'error': '(NO IAM ACCESS)', 'functions': [], 'event_source_mappings': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_lambda_data: {e}")
            raise e