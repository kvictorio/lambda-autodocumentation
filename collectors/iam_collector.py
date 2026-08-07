# collectors/iam_collector.py
from botocore.exceptions import ClientError
from utils import get_environment_from_name, get_client, safe_tags

ADMIN_POLICY_ARN = 'arn:aws:iam::aws:policy/AdministratorAccess'


def _statement_is_risky(statement):
    """A single policy statement is risky if it Allows Action:* on Resource:*."""
    if statement.get('Effect') != 'Allow':
        return False
    actions = statement.get('Action', [])
    if isinstance(actions, str):
        actions = [actions]
    resources = statement.get('Resource', [])
    if isinstance(resources, str):
        resources = [resources]
    return '*' in actions and '*' in resources


def _document_is_risky(document):
    """Checks every statement in a policy document for wildcard admin access."""
    if not document:
        return False
    statements = document.get('Statement', [])
    if isinstance(statements, dict):
        statements = [statements]
    return any(_statement_is_risky(s) for s in statements)


def get_iam_data():
    """
    Fetches IAM roles and users, including their attached/inline policies.
    Flags any policy that grants wildcard admin-level access
    ("Effect": "Allow", "Action": "*", "Resource": "*") or the AWS-managed
    AdministratorAccess policy, and flags users without MFA enabled.
    Includes error handling for missing IAM permissions.
    """
    try:
        iam_client = get_client('iam')
        roles_data = []
        users_data = []
        policy_doc_cache = {}  # policy_arn -> document, avoids re-fetching shared/attached policies

        def get_policy_document(policy_arn):
            if policy_arn in policy_doc_cache:
                return policy_doc_cache[policy_arn]
            try:
                policy = iam_client.get_policy(PolicyArn=policy_arn)['Policy']
                version_id = policy['DefaultVersionId']
                version = iam_client.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
                document = version['PolicyVersion']['Document']
            except ClientError:
                document = None
            policy_doc_cache[policy_arn] = document
            return document

        # --- IAM Roles ---
        paginator_roles = iam_client.get_paginator('list_roles')
        for page in paginator_roles.paginate():
            for role in page['Roles']:
                role_name = role['RoleName']
                # list_roles does NOT return tags, so role.get('Tags') was always
                # empty and environment detection silently fell back to the name.
                tags = safe_tags(
                    lambda n=role_name: iam_client.list_role_tags(RoleName=n).get('Tags', []),
                    f"IAM role {role_name}"
                )

                risky_policies = []
                has_admin_access = False

                attached = iam_client.list_attached_role_policies(RoleName=role_name).get('AttachedPolicies', [])
                attached_names = []
                for policy in attached:
                    attached_names.append(policy['PolicyName'])
                    if policy['PolicyArn'] == ADMIN_POLICY_ARN:
                        has_admin_access = True
                        risky_policies.append(f"{policy['PolicyName']} (AWS Managed AdministratorAccess)")
                    else:
                        document = get_policy_document(policy['PolicyArn'])
                        if _document_is_risky(document):
                            has_admin_access = True
                            risky_policies.append(f"{policy['PolicyName']} (wildcard Action+Resource)")

                inline_names = iam_client.list_role_policies(RoleName=role_name).get('PolicyNames', [])
                for policy_name in inline_names:
                    document = iam_client.get_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    ).get('PolicyDocument')
                    if _document_is_risky(document):
                        has_admin_access = True
                        risky_policies.append(f"{policy_name} (inline, wildcard Action+Resource)")

                roles_data.append({
                    'Name': role_name,
                    'Arn': role['Arn'],
                    'CreateDate': role['CreateDate'].strftime('%Y-%m-%d'),
                    'AttachedPolicies': attached_names,
                    'InlinePolicyCount': len(inline_names),
                    'RiskyPolicies': risky_policies,
                    'HasAdminAccess': has_admin_access,
                    'Environment': get_environment_from_name(role_name, tags)
                })

        # --- IAM Users ---
        paginator_users = iam_client.get_paginator('list_users')
        for page in paginator_users.paginate():
            for user in page['Users']:
                user_name = user['UserName']
                # list_users does NOT return tags either.
                tags = safe_tags(
                    lambda n=user_name: iam_client.list_user_tags(UserName=n).get('Tags', []),
                    f"IAM user {user_name}"
                )

                mfa_devices = iam_client.list_mfa_devices(UserName=user_name).get('MFADevices', [])
                access_keys = iam_client.list_access_keys(UserName=user_name).get('AccessKeyMetadata', [])
                active_key_count = len([k for k in access_keys if k['Status'] == 'Active'])

                attached = iam_client.list_attached_user_policies(UserName=user_name).get('AttachedPolicies', [])
                has_admin_access = any(p['PolicyArn'] == ADMIN_POLICY_ARN for p in attached)

                users_data.append({
                    'Name': user_name,
                    'Arn': user['Arn'],
                    'CreateDate': user['CreateDate'].strftime('%Y-%m-%d'),
                    'MfaEnabled': len(mfa_devices) > 0,
                    'ActiveAccessKeys': active_key_count,
                    'AttachedPolicies': [p['PolicyName'] for p in attached],
                    'HasAdminAccess': has_admin_access,
                    'Environment': get_environment_from_name(user_name, tags)
                })

        return {'roles': roles_data, 'users': users_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for IAM services. Skipping IAM data collection.")
            return {'error': '(NO IAM ACCESS)', 'roles': [], 'users': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_iam_data: {e}")
            raise e
