# collectors/eventbridge_collector.py
from botocore.exceptions import ClientError
from utils import get_environment_from_name, get_client, safe_tags


def get_eventbridge_data():
    """
    Fetches detailed information about EventBridge event buses, their rules,
    and each rule's targets (e.g. Lambda functions, SQS queues, Step Functions).
    Includes error handling for missing IAM permissions.
    """
    try:
        events_client = get_client('events')
        buses_data = []

        paginator_buses = events_client.get_paginator('list_event_buses')
        for page in paginator_buses.paginate():
            for bus in page.get('EventBuses', []):
                bus_name = bus['Name']

                rules_data = []
                paginator_rules = events_client.get_paginator('list_rules')
                for rule_page in paginator_rules.paginate(EventBusName=bus_name):
                    for rule in rule_page.get('Rules', []):
                        rule_name = rule['Name']

                        targets = events_client.list_targets_by_rule(
                            Rule=rule_name, EventBusName=bus_name
                        ).get('Targets', [])
                        targets_data = [{'Id': t.get('Id', 'N/A'), 'Arn': t.get('Arn', 'N/A')} for t in targets]

                        rules_data.append({
                            'Name': rule_name,
                            'State': rule.get('State', 'N/A'),
                            'ScheduleExpression': rule.get('ScheduleExpression', 'N/A'),
                            'HasEventPattern': 'EventPattern' in rule,
                            'Targets': targets_data
                        })

                bus_arn = bus.get('Arn')
                tags = safe_tags(
                    lambda arn=bus_arn: events_client.list_tags_for_resource(ResourceARN=arn).get('Tags', []),
                    f"EventBridge bus {bus_name}"
                ) if bus_arn else None

                buses_data.append({
                    'Name': bus_name,
                    'Arn': bus.get('Arn', 'N/A'),
                    'Rules': rules_data,
                    'Environment': get_environment_from_name(bus_name, tags)
                })

        return {'event_buses': buses_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for EventBridge services. Skipping EventBridge data collection.")
            return {'error': '(NO IAM ACCESS)', 'event_buses': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_eventbridge_data: {e}")
            raise e
