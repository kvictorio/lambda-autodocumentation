# lambda_function.py
import os
import json
import traceback
from datetime import datetime

from utils import get_client

# Import all our custom functions from the new modules
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
from collectors.iam_collector import get_iam_data
from collectors.sns_collector import get_sns_data
from collectors.eventbridge_collector import get_eventbridge_data
from reporting.markdown_report import generate_text_report
from reporting.mermaid_diagram import generate_mermaid_diagram

# Environment variable for the S3 bucket
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
if not S3_BUCKET_NAME:
    raise ValueError("S3_BUCKET_NAME environment variable not set.")

def upload_to_s3(content, bucket, object_name):
    """Uploads a string content to an S3 object."""
    s3_client = get_client('s3')
    try:
        s3_client.put_object(Body=content, Bucket=bucket, Key=object_name)
        print(f"Successfully uploaded {object_name} to {bucket}")
    except Exception as e:
        print(f"Error uploading file: {e}")
        raise e

    # Fallback shape returned for a collector that fails, keyed by the same
    # dict keys lambda_function.py/reporting modules expect to find populated
    # (as empty lists) so downstream code never KeyErrors on a missing field.
COLLECTOR_FALLBACKS = {
    'ec2': {'instances': [], 'security_groups': [], 'subnet_map': {}, 'sg_map': {}},
    'lambda': {'functions': [], 'event_source_mappings': []},
    's3': {'buckets': []},
    'apigateway': {'apis': []},
    'vpc': {'vpcs': []},
    'rds': {'instances': []},
    'cognito': {'user_pools': []},
    'container': {'ecr_repositories': [], 'eks_clusters': [], 'ecs_clusters': []},
    'neptune': {'clusters': []},
    'dynamodb': {'tables': []},
    'elasticache': {'clusters': []},
    'queues': {'sqs_queues': [], 'kinesis_streams': [], 'firehose_streams': []},
    'iam': {'roles': [], 'users': []},
    'sns': {'topics': []},
    'eventbridge': {'event_buses': []},
}


def safe_collect(collector_name, collector_func):
    """
    Runs a single collector in isolation. If it raises ANYTHING (throttling
    that outlasts the retry budget, an unexpected ClientError, a bug in the
    collector itself, etc.), the failure is logged and a well-formed empty
    result is returned instead - so the other 14 collectors and the rest of
    the report generation still complete successfully.
    """
    try:
        return collector_func()
    except Exception as e:
        print(f"ERROR: Collector '{collector_name}' failed unexpectedly and was skipped: {e}")
        traceback.print_exc()
        fallback = dict(COLLECTOR_FALLBACKS[collector_name])
        fallback['error'] = f'(COLLECTION FAILED: {type(e).__name__}: {e})'
        return fallback


def _emit_dry_run(timestamp, now, failed_collectors):
    """Builds a review sheet of every categorisation decision made this run."""
    from utils import ENV_AUDIT

    by_env = {}
    for entry in ENV_AUDIT:
        by_env.setdefault(entry['environment'], []).append(entry)

    lines = [
        "# Environment Detection - Dry Run",
        f"_Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}. No reports were written._\n",
        "Review this before trusting a full run. Anything landing in `no-category` "
        "or flagged ambiguous below needs either a proper `Environment` tag or an "
        "`ENV_ALIASES_JSON` override.\n",
    ]

    if failed_collectors:
        lines.append(f"> ⚠️ Collectors that failed this run: **{', '.join(sorted(failed_collectors))}**\n")

    total = len(ENV_AUDIT)
    by_tag = sum(1 for e in ENV_AUDIT if e['source'].startswith('tag:'))
    by_name = sum(1 for e in ENV_AUDIT if e['source'] == 'name')
    uncategorized = len(by_env.get('no-category', []))
    lines.append("## Summary\n")
    lines.append("| Metric | Count |")
    lines.append("| :--- | ---: |")
    lines.append(f"| Resources categorised | {total} |")
    lines.append(f"| Resolved from a tag (reliable) | {by_tag} |")
    lines.append(f"| Guessed from the name (verify these) | {by_name} |")
    lines.append(f"| Uncategorised | {uncategorized} |")

    ambiguous = [e for e in ENV_AUDIT if e.get('ambiguous')]
    if ambiguous:
        lines.append("\n## ⚠️ Ambiguous names (matched more than one environment)\n")
        lines.append("| Resource | Matched | Resolved to |")
        lines.append("| :--- | :--- | :--- |")
        for e in sorted(ambiguous, key=lambda x: x['name']):
            lines.append(f"| `{e['name']}` | {', '.join(e.get('all_matches') or [])} | **{e['environment']}** |")

    lines.append("\n## Detected environments\n")
    for env_name in sorted(by_env):
        entries = by_env[env_name]
        lines.append(f"\n### `{env_name}` ({len(entries)} resources)\n")
        lines.append("| Resource | Detected via |")
        lines.append("| :--- | :--- |")
        for e in sorted(entries, key=lambda x: x['name']):
            lines.append(f"| `{e['name']}` | {e['source']} |")

    content = "\n".join(lines)
    key = f'reports/{timestamp}/DRY-RUN-environment-detection.md'
    upload_to_s3(content, S3_BUCKET_NAME, key)
    print(f"Dry run complete: {total} resources, {by_name} name-guessed, {uncategorized} uncategorised.")
    return {
        'statusCode': 200,
        'body': json.dumps({
            'mode': 'dry_run',
            'resources_categorized': total,
            'resolved_by_tag': by_tag,
            'guessed_by_name': by_name,
            'uncategorized': uncategorized,
            'ambiguous': len(ambiguous),
            'report': f's3://{S3_BUCKET_NAME}/{key}',
        })
    }


def lambda_handler(event, context):
    """Main function executed by AWS Lambda."""
    print("Starting infrastructure documentation process...")
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d")

    # 1. Fetch data from all services into a single dictionary.
    # Each collector runs independently via safe_collect - a failure in one
    # (e.g. IAM throttling) no longer prevents the other 14 from completing
    # or the report from being generated and uploaded.
    all_resources = {
        'ec2': safe_collect('ec2', get_ec2_data),
        'lambda': safe_collect('lambda', get_lambda_data),
        's3': safe_collect('s3', get_s3_data),
        'apigateway': safe_collect('apigateway', get_apigateway_data),
        'vpc': safe_collect('vpc', get_vpc_data),
        'rds': safe_collect('rds', get_rds_data),
        'cognito': safe_collect('cognito', get_cognito_data),
        'container': safe_collect('container', get_container_data),
        'neptune': safe_collect('neptune', get_neptune_data),
        'dynamodb': safe_collect('dynamodb', get_dynamodb_data),
        'elasticache': safe_collect('elasticache', get_elasticache_data),
        'queues': safe_collect('queues', get_queues_data),
        'iam': safe_collect('iam', get_iam_data),
        'sns': safe_collect('sns', get_sns_data),
        'eventbridge': safe_collect('eventbridge', get_eventbridge_data),
    }

    failed_collectors = [name for name, data in all_resources.items() if data.get('error', '').startswith('(COLLECTION FAILED')]
    if failed_collectors:
        print(f"WARNING: The following collectors failed and were skipped: {', '.join(failed_collectors)}")

    # 1b. Dry-run mode: emit only how each resource was categorised, so the
    # environment detection can be sanity-checked against a project's real
    # naming/tagging conventions BEFORE trusting a full report.
    # Trigger with {"dry_run": true} in the test event, or DRY_RUN=true.
    dry_run = bool(event.get('dry_run')) if isinstance(event, dict) else False
    dry_run = dry_run or os.environ.get('DRY_RUN', '').lower() in ('1', 'true', 'yes')
    if dry_run:
        return _emit_dry_run(timestamp, now, failed_collectors)
    
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
        'firehose_streams': all_resources['queues'].get('firehose_streams', []),
        'iam_roles': all_resources['iam'].get('roles', []),
        'iam_users': all_resources['iam'].get('users', []),
        'sns_topics': all_resources['sns'].get('topics', []),
        'eventbridge_buses': all_resources['eventbridge'].get('event_buses', [])
    }

    for category_name, resource_list in resource_map.items():
        if not resource_list:
            continue
        for resource in resource_list:
            env = resource.get('Environment', 'no-category')
            if env not in categorized_data: categorized_data[env] = {}
            if category_name not in categorized_data[env]: categorized_data[env][category_name] = []
            categorized_data[env][category_name].append(resource)
    
    # 3. Build cross-reference maps
    sg_cross_reference = {}
    for instance in resource_map['instances']:
        for sg_id in instance.get('SecurityGroups', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"EC2: {instance['Name']}")
    for rds in resource_map['rds_instances']:
        for sg_id in rds.get('SecurityGroupIds', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"RDS: {rds['Name']}")
    for func in resource_map['functions']:
        for sg_id in func.get('SecurityGroupIds', []):
            if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
            sg_cross_reference[sg_id].append(f"Lambda: {func['Name']}")
    for vpc in resource_map['vpcs']:
        for lb in vpc.get('LoadBalancers', []):
            for sg_id in lb.get('SecurityGroupIds', []):
                if sg_id not in sg_cross_reference: sg_cross_reference[sg_id] = []
                sg_cross_reference[sg_id].append(f"Load Balancer: {lb['Name']}")

    lambda_db_connections = []
    db_endpoints = {}
    for rds in all_resources['rds'].get('instances', []): db_endpoints[rds['Endpoint']] = "rds_" + rds['Name'].replace('-', '_')
    for neptune in all_resources['neptune'].get('clusters', []): db_endpoints[neptune['Endpoint']] = "neptune_" + neptune['Name'].replace('-', '_')
    for elasticache in all_resources['elasticache'].get('clusters', []): db_endpoints[elasticache['Endpoint']] = "elasticache_" + elasticache['Name'].replace('-', '_')
    
    for func in all_resources['lambda'].get('functions', []):
        func_node_id = "lambda_" + func['Name'].replace('-', '_').replace('.', '_')
        for key, value in func.get('EnvironmentVariables', {}).items():
            for endpoint, db_node_id in db_endpoints.items():
                if endpoint in value:
                    lambda_db_connections.append({'from': func_node_id, 'to': db_node_id, 'label': key})
                    break
            
    # 4. Generate and upload reports
    main_readme_content = [f"# AWS Infrastructure Report", f"_Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}_", "\n## Discovered Environments\n"]
    if not categorized_data:
        main_readme_content.append("\n_No resources were found across the tracked environments, or access was denied for all services._")

    if failed_collectors:
        main_readme_content.append("\n## ⚠️ Incomplete Data\n")
        main_readme_content.append(f"The following collectors failed and were skipped, so this report is incomplete for those services: **{', '.join(sorted(failed_collectors))}**.")
        main_readme_content.append("Check the Lambda's CloudWatch logs for this run for the specific error.\n")

    for env_name, env_data in sorted(categorized_data.items()):
        print(f"Generating documents for environment: {env_name}")
        main_readme_content.append(f"* [{env_name.upper()}](./{env_name}-documentation.md)")

        report_content = generate_text_report(env_name, env_data, all_resources, sg_cross_reference)
        diagram_content = generate_mermaid_diagram(env_name, env_data, all_resources, lambda_db_connections)

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