import boto3
from utils import get_environment_from_name

def get_ec2_data():
    """
    Fetches data for EC2 instances, Security Groups, and Subnets.
    Also returns maps to resolve Subnet and SG IDs to their names.
    """
    ec2_client = boto3.client('ec2')
    
    instances_data = []
    sg_data = []
    
    # --- Create Lookup Maps ---
    subnet_map = {}
    subnets_response = ec2_client.describe_subnets()
    for subnet in subnets_response.get('Subnets', []):
        name = next((tag['Value'] for tag in subnet.get('Tags', []) if tag['Key'] == 'Name'), subnet['SubnetId'])
        subnet_map[subnet['SubnetId']] = name

    sg_map = {}
    paginator_sg = ec2_client.get_paginator('describe_security_groups')
    for page in paginator_sg.paginate():
        for sg in page['SecurityGroups']:
            sg_name = sg.get('GroupName', sg['GroupId'])
            sg_map[sg['GroupId']] = sg_name
            sg_data.append({
                'Name': sg_name,
                'GroupId': sg['GroupId'],
                'InboundRules': sg.get('IpPermissions', []),
                'OutboundRules': sg.get('IpPermissionsEgress', []),
                'Environment': get_environment_from_name(sg_name, sg.get('Tags', []))
            })

    # --- Get EC2 Instances ---
    paginator_inst = ec2_client.get_paginator('describe_instances')
    for page in paginator_inst.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]):
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), instance['InstanceId'])
                instances_data.append({
                    'Name': name,
                    'InstanceId': instance['InstanceId'],
                    'SubnetId': instance.get('SubnetId', 'N/A'),
                    'SecurityGroups': [sg['GroupId'] for sg in instance.get('SecurityGroups', [])],
                    'Environment': get_environment_from_name(name, instance.get('Tags', []))
                })

    return {
        'instances': instances_data, 
        'security_groups': sg_data,
        'subnet_map': subnet_map,
        'sg_map': sg_map
    }