# collectors/lambda_collector.py
import boto3
from utils import get_environment_from_name

def get_lambda_data():
    lambda_client = boto3.client('lambda')
    functions_data = []
    paginator = lambda_client.get_paginator('list_functions')
    for page in paginator.paginate():
        for function in page['Functions']:
            functions_data.append({
                'Name': function['FunctionName'],
                'Runtime': function.get('Runtime', 'Container/Unknown'),
                'Environment': get_environment_from_name(function['FunctionName'])
            })
    return {'functions': functions_data}