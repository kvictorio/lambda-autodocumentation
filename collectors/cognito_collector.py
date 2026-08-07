# collectors/cognito_collector.py
from botocore.exceptions import ClientError
from utils import get_environment_from_name, get_client, safe_tags

def get_cognito_data():
    """
    Fetches detailed information about Cognito User Pools and their App Clients.
    Includes error handling for missing IAM permissions.
    """
    try:
        cognito_client = get_client('cognito-idp')
        user_pools_data = []
        
        paginator = cognito_client.get_paginator('list_user_pools')
        for page in paginator.paginate(MaxResults=50):
            for pool in page['UserPools']:
                pool_id = pool['Id']
                pool_name = pool['Name']
                
                # Get app clients for each user pool
                app_clients = []
                client_paginator = cognito_client.get_paginator('list_user_pool_clients')
                for client_page in client_paginator.paginate(UserPoolId=pool_id, MaxResults=50):
                    for client in client_page.get('UserPoolClients', []):
                        app_clients.append({
                            'ClientName': client['ClientName'],
                            'ClientId': client['ClientId']
                        })

                # list_user_pools omits tags; describe_user_pool returns them.
                tags = safe_tags(
                    lambda pid=pool_id: cognito_client.describe_user_pool(UserPoolId=pid).get('UserPool', {}).get('UserPoolTags', {}),
                    f"Cognito user pool {pool_name}"
                )

                user_pools_data.append({
                    'Name': pool_name,
                    'Id': pool_id,
                    'AppClients': app_clients,
                    'Environment': get_environment_from_name(pool_name, tags)
                })
        
        return {'user_pools': user_pools_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Cognito services. Skipping Cognito data collection.")
            return {'error': '(NO IAM ACCESS)', 'user_pools': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_cognito_data: {e}")
            raise e