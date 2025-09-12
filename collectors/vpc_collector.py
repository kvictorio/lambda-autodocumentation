# collectors/vpc_collector.py
import boto3
from utils import get_environment_from_name

def get_vpc_data():
    """Fetches detailed information about VPCs and their networking components."""
    ec2_client = boto3.client('ec2')
    elbv2_client = boto3.client('elbv2')
    
    vpcs_data = {}

    # 1. Get all VPCs
    vpcs_response = ec2_client.describe_vpcs()
    for vpc in vpcs_response.get('Vpcs', []):
        vpc_id = vpc['VpcId']
        name = next((tag['Value'] for tag in vpc.get('Tags', []) if tag['Key'] == 'Name'), vpc_id)
        vpcs_data[vpc_id] = {
            'VpcId': vpc_id,
            'Name': name,
            'CidrBlock': vpc['CidrBlock'],
            'IsDefault': vpc['IsDefault'],
            'Environment': get_environment_from_name(name, vpc.get('Tags', [])),
            'Subnets': [],
            'RouteTables': [],
            'LoadBalancers': []
        }

    # 2. Get all Subnets and associate them with VPCs
    subnets_response = ec2_client.describe_subnets()
    for subnet in subnets_response.get('Subnets', []):
        vpc_id = subnet['VpcId']
        if vpc_id in vpcs_data:
            vpcs_data[vpc_id]['Subnets'].append({
                'SubnetId': subnet['SubnetId'],
                'CidrBlock': subnet['CidrBlock'],
                'AvailabilityZone': subnet['AvailabilityZone']
            })

    # 3. Get all Route Tables and associate them with VPCs
    routes_response = ec2_client.describe_route_tables()
    for table in routes_response.get('RouteTables', []):
        vpc_id = table['VpcId']
        if vpc_id in vpcs_data:
            routes = []
            for route in table.get('Routes', []):
                routes.append({
                    'Destination': route.get('DestinationCidrBlock', 'N/A'),
                    'Target': route.get('GatewayId') or route.get('TransitGatewayId') or route.get('NatGatewayId') or 'N/A'
                })
            vpcs_data[vpc_id]['RouteTables'].append({
                'RouteTableId': table['RouteTableId'],
                'Routes': routes
            })

    # 4. Get all Load Balancers (v2) and associate them with VPCs
    lbs_response = elbv2_client.describe_load_balancers()
    for lb in lbs_response.get('LoadBalancers', []):
        vpc_id = lb['VpcId']
        if vpc_id in vpcs_data:
            lb_arn = lb['LoadBalancerArn']
            
            # Get Listeners for this LB
            listeners_response = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn)
            listeners = []
            for listener in listeners_response.get('Listeners', []):
                listeners.append({
                    'Port': listener['Port'],
                    'Protocol': listener['Protocol'],
                    'ListenerArn': listener['ListenerArn']
                })

            vpcs_data[vpc_id]['LoadBalancers'].append({
                'Name': lb['LoadBalancerName'],
                'DNSName': lb['DNSName'],
                'Type': lb['Type'],
                'Scheme': lb['Scheme'],
                'Listeners': listeners
            })
            
    # Convert the dictionary to a list for easier processing later
    return {'vpcs': list(vpcs_data.values())}