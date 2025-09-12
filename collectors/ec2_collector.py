# collectors/ec2_collector.py
import boto3
from utils import get_environment_from_name

def get_ec2_data():
    ec2_client = boto3.client('ec2')
    instances_data = []
    sg_data = []
    paginator = ec2_client.get_paginator('describe_instances')
    for page in paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]):
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), instance['InstanceId'])
                instances_data.append({
                    'Name': name,
                    'InstanceId': instance['InstanceId'],
                    'SubnetId': instance.get('SubnetId', 'N/A'), # <-- ADD THIS LINE
                    'SecurityGroups': [sg['GroupId'] for sg in instance.get('SecurityGroups', [])],
                    'Environment': get_environment_from_name(name, instance.get('Tags', []))
                })
    
    # The rest of the function for security groups remains the same...
    paginator = ec2_client.get_paginator('describe_security_groups')
    for page in paginator.paginate():
        for sg in page['SecurityGroups']:
            sg_data.append({
                'Name': sg.get('GroupName', sg['GroupId']),
                'GroupId': sg['GroupId'],
                'InboundRules': sg.get('IpPermissions', []),
                'OutboundRules': sg.get('IpPermissionsEgress', []),
                'Environment': get_environment_from_name(sg.get('GroupName', ''), sg.get('Tags', []))
            })
    return {'instances': instances_data, 'security_groups': sg_data}