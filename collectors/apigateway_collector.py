# collectors/apigateway_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_apigateway_data():
    """
    Fetches information about API Gateway v1 (REST) and v2 (HTTP/WebSocket) APIs.
    Includes error handling for missing IAM permissions.
    """
    try:
        apis_data = []
        
        # --- API Gateway v2 (HTTP/WebSocket) ---
        # This requires apigatewayv2:Get* permissions
        apigw_v2_client = boto3.client('apigatewayv2')
        paginator_v2 = apigw_v2_client.get_paginator('get_apis')
        for page in paginator_v2.paginate():
            for api in page['Items']:
                api_id = api['ApiId']
                
                # Get routes
                routes_response = apigw_v2_client.get_routes(ApiId=api_id)
                routes = [f"{r['RouteKey']}" for r in routes_response.get('Items', [])]
                
                # Get authorizers
                auth_response = apigw_v2_client.get_authorizers(ApiId=api_id)
                authorizers = [f"{a['Name']} ({a['AuthorizerType']})" for a in auth_response.get('Items', [])]
                
                apis_data.append({
                    'Name': api['Name'],
                    'ApiId': api_id,
                    'ProtocolType': api['ProtocolType'],
                    'Routes': routes,
                    'Authorizers': authorizers,
                    'Environment': get_environment_from_name(api['Name'], api.get('Tags', {}))
                })

        # --- API Gateway v1 (REST) ---
        # This requires apigateway:GET permission
        apigw_v1_client = boto3.client('apigateway')
        paginator_v1 = apigw_v1_client.get_paginator('get_rest_apis')
        for page in paginator_v1.paginate():
            for api in page['items']:
                api_id = api['id']
                
                # Get resources (routes)
                res_response = apigw_v1_client.get_resources(restApiId=api_id)
                routes = [f"{res['path']}" for res in res_response.get('items', [])]

                # Get authorizers
                auth_response = apigw_v1_client.get_authorizers(restApiId=api_id)
                authorizers = [f"{a['name']} ({a['type']})" for a in auth_response.get('items', [])]
                
                apis_data.append({
                    'Name': api['name'],
                    'ApiId': api_id,
                    'ProtocolType': 'REST',
                    'Routes': routes,
                    'Authorizers': authorizers,
                    'Environment': get_environment_from_name(api['name'], api.get('tags', {}))
                })

        return {'apis': apis_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for API Gateway services. Skipping API Gateway data collection.")
            return {'error': '(NO IAM ACCESS)', 'apis': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_apigateway_data: {e}")
            raise e