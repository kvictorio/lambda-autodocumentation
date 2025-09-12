import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_apigateway_data():
    """
    Fetches detailed information about API Gateway routes, authorizers, and integrations.
    Handles both v1 (REST) and v2 (HTTP/WebSocket) APIs.
    """
    try:
        apis_data = []
        
        # --- API Gateway v2 (HTTP/WebSocket) ---
        apigw_v2_client = boto3.client('apigatewayv2')
        for api in apigw_v2_client.get_apis()['Items']:
            api_id = api['ApiId']
            
            authorizers_map = {a['AuthorizerId']: a['Name'] for a in apigw_v2_client.get_authorizers(ApiId=api_id).get('Items', [])}
            integrations = apigw_v2_client.get_integrations(ApiId=api_id).get('Items', [])
            
            routes_details = []
            for route in apigw_v2_client.get_routes(ApiId=api_id).get('Items', []):
                target = route.get('Target', 'N/A')
                if 'integrations/' in target:
                    integration_id = target.split('/')[-1]
                    # Find the integration details
                    integration_detail = next((i for i in integrations if i['IntegrationId'] == integration_id), None)
                    if integration_detail and 'IntegrationUri' in integration_detail:
                        target = f"Lambda: `{integration_detail['IntegrationUri'].split(':')[-1].split('}')[0]}`"

                routes_details.append({
                    'RouteKey': route['RouteKey'],
                    'Authorizer': authorizers_map.get(route.get('AuthorizerId'), 'None'),
                    'Target': target
                })

            apis_data.append({
                'Name': api['Name'], 'ApiId': api_id, 'ProtocolType': api['ProtocolType'],
                'Routes': sorted(routes_details, key=lambda x: x['RouteKey']),
                'Environment': get_environment_from_name(api['Name'], api.get('Tags', {}))
            })

        # --- API Gateway v1 (REST) ---
        apigw_v1_client = boto3.client('apigateway')
        for api in apigw_v1_client.get_rest_apis()['items']:
            api_id = api['id']
            authorizers_map = {a['id']: a['name'] for a in apigw_v1_client.get_authorizers(restApiId=api_id).get('items', [])}
            
            routes_details = []
            resources = apigw_v1_client.get_resources(restApiId=api_id).get('items', [])
            for resource in resources:
                if 'resourceMethods' not in resource: continue
                for method_name, method_details in resource.get('resourceMethods', {}).items():
                    integration = method_details.get('methodIntegration', {})
                    target = integration.get('uri', 'N/A').split('/')[-1]
                    if 'arn:' in target:
                        target = f"Lambda: `{target.split(':')[-1]}`"

                    routes_details.append({
                        'RouteKey': f"{method_name} {resource['path']}",
                        'Authorizer': authorizers_map.get(method_details.get('authorizerId'), 'None'),
                        'Target': target
                    })

            apis_data.append({
                'Name': api['name'], 'ApiId': api_id, 'ProtocolType': 'REST',
                'Routes': sorted(routes_details, key=lambda x: x['RouteKey']),
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