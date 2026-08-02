# collectors/sns_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name


def get_sns_data():
    """
    Fetches detailed information about SNS topics and their subscriptions.
    Includes error handling for missing IAM permissions.
    """
    try:
        sns_client = boto3.client('sns')
        topics_data = []

        paginator_topics = sns_client.get_paginator('list_topics')
        for page in paginator_topics.paginate():
            for topic in page.get('Topics', []):
                topic_arn = topic['TopicArn']
                topic_name = topic_arn.split(':')[-1]

                attrs = sns_client.get_topic_attributes(TopicArn=topic_arn).get('Attributes', {})

                subscriptions = []
                paginator_subs = sns_client.get_paginator('list_subscriptions_by_topic')
                for sub_page in paginator_subs.paginate(TopicArn=topic_arn):
                    for sub in sub_page.get('Subscriptions', []):
                        subscriptions.append({
                            'Protocol': sub.get('Protocol', 'N/A'),
                            'Endpoint': sub.get('Endpoint', 'N/A'),
                            'SubscriptionArn': sub.get('SubscriptionArn', 'N/A')
                        })

                topics_data.append({
                    'Name': topic_name,
                    'TopicArn': topic_arn,
                    'DisplayName': attrs.get('DisplayName', ''),
                    'IsFifo': topic_name.endswith('.fifo'),
                    'SubscriptionsConfirmed': attrs.get('SubscriptionsConfirmed', 'N/A'),
                    'Subscriptions': subscriptions,
                    'Environment': get_environment_from_name(topic_name)
                })

        return {'topics': topics_data}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for SNS services. Skipping SNS data collection.")
            return {'error': '(NO IAM ACCESS)', 'topics': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_sns_data: {e}")
            raise e
