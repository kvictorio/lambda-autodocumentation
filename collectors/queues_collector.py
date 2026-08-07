# collectors/queues_collector.py
from botocore.exceptions import ClientError
from utils import get_environment_from_name, get_client, safe_tags

def get_queues_data():
    """
    Fetches detailed information about SQS, Kinesis Streams, and Kinesis Firehose.
    Includes error handling for missing IAM permissions.
    """
    try:
        sqs_client = get_client('sqs')
        kinesis_client = get_client('kinesis')
        firehose_client = get_client('firehose')
        
        sqs_queues = []
        kinesis_streams = []
        firehose_streams = []

        # 1. Get SQS Queues (this part was correct)
        paginator_sqs = sqs_client.get_paginator('list_queues')
        for page in paginator_sqs.paginate():
            for queue_url in page.get('QueueUrls', []):
                queue_name = queue_url.split('/')[-1]
                attrs = sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['All']).get('Attributes', {})
                tags = safe_tags(
                    lambda url=queue_url: sqs_client.list_queue_tags(QueueUrl=url).get('Tags', {}),
                    f"SQS queue {queue_name}"
                )

                sqs_queues.append({
                    'Name': queue_name,
                    'Type': 'Standard' if 'FifoQueue' not in attrs else 'FIFO',
                    'MessageCount': attrs.get('ApproximateNumberOfMessages', 'N/A'),
                    'Environment': get_environment_from_name(queue_name, tags)
                })
        
        # 2. Get Kinesis Data Streams (this part was correct)
        paginator_kinesis = kinesis_client.get_paginator('list_streams')
        for page in paginator_kinesis.paginate():
            for stream_name in page.get('StreamNames', []):
                details = kinesis_client.describe_stream(StreamName=stream_name).get('StreamDescription', {})
                tags = safe_tags(
                    lambda n=stream_name: kinesis_client.list_tags_for_stream(StreamName=n).get('Tags', []),
                    f"Kinesis stream {stream_name}"
                )

                kinesis_streams.append({
                    'Name': stream_name,
                    'Status': details.get('StreamStatus'),
                    'Shards': len(details.get('Shards', [])),
                    'Environment': get_environment_from_name(stream_name, tags)
                })

        # 3. Get Kinesis Data Firehose Delivery Streams using manual pagination
        all_stream_names = []
        has_more_streams = True
        last_stream_name = None
        while has_more_streams:
            if last_stream_name:
                response = firehose_client.list_delivery_streams(ExclusiveStartDeliveryStreamName=last_stream_name)
            else:
                response = firehose_client.list_delivery_streams()
            
            all_stream_names.extend(response.get('DeliveryStreamNames', []))
            has_more_streams = response.get('HasMoreDeliveryStreams', False)
            if has_more_streams:
                last_stream_name = all_stream_names[-1]

        for stream_name in all_stream_names:
            details = firehose_client.describe_delivery_stream(DeliveryStreamName=stream_name).get('DeliveryStreamDescription', {})
            destination_type = 'N/A'
            if details.get('Destinations'):
                dest_keys = [key for key in details['Destinations'][0] if 'DestinationDescription' in key]
                if dest_keys:
                    destination_type = dest_keys[0].replace('DestinationDescription', '')
            fh_tags = safe_tags(
                lambda n=stream_name: firehose_client.list_tags_for_delivery_stream(DeliveryStreamName=n).get('Tags', []),
                f"Firehose stream {stream_name}"
            )

            firehose_streams.append({
                'Name': stream_name,
                'Status': details.get('DeliveryStreamStatus'),
                'Destination': destination_type,
                'Environment': get_environment_from_name(stream_name, fh_tags)
            })

        return {
            'sqs_queues': sqs_queues,
            'kinesis_streams': kinesis_streams,
            'firehose_streams': firehose_streams
        }
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for Queue/Stream services. Skipping.")
            return {'error': '(NO IAM ACCESS)', 'sqs_queues': [], 'kinesis_streams': [], 'firehose_streams': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_queues_data: {e}")
            raise e