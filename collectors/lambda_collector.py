# collectors/lambda_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_lambda_data():
    """
    Fetches detailed information about Lambda functions, including their VPC configuration.
    Includes error handling for missing IAM permissions.
    """
    try:
        lambda_client = boto3.client('lambda')
        functions_data = []
        
        # This API call requires lambda:ListFunctions permission
        paginator = lambda_client.get_paginator('list_functions')
        for page in paginator.paginate():
            for function in page['Functions']:
                vpc_config = function.get('VpcConfig')
                
                function_details = {
                    'Name': function['FunctionName'],
                    'Runtime': function.get('Runtime', 'Container/Unknown'),
                    'Environment': get_environment_from_name(function['FunctionName']),
                    'VpcId': None,
                    'SubnetIds': [],
                    'SecurityGroupIds': []
                }

                if vpc_config and vpc_config.get('VpcId'):
                    function_details['VpcId'] = vpc_config.get('VpcId')
                    function_details['SubnetIds'] = vpc_config.get('SubnetIds', [])
                    function_details['SecurityGroupIds'] = vpc_config.get('SecurityGroupIds', [])
                
                functions_data.append(function_details)
                
        return {'functions': functions_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Lambda services. Skipping Lambda data collection.")
            return {'error': '(NO IAM ACCESS)', 'functions': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_lambda_data: {e}")
            raise e