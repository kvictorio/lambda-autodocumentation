import boto3
from utils import get_environment_from_name

def get_lambda_data():
    """
    Fetches detailed information about Lambda functions, including their VPC configuration.
    """
    lambda_client = boto3.client('lambda')
    functions_data = []
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