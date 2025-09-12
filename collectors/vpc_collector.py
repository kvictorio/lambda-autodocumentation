# collectors/vpc_collector.py
import boto3
from botocore.exceptions import ClientError
from utils import get_environment_from_name

def get_vpc_data():
    """
    Fetches detailed information about VPCs and their networking components.
    Includes error handling for missing IAM permissions.
    """
    try:
        ec2_client = boto3.client('ec2')
        elbv2_client = boto3.client('elbv2')
        
        vpcs_data = {}

        # Requires ec2:DescribeVpcs
        vpcs_response = ec2_client.describe_vpcs()
        for vpc in vpcs_response.get('Vpcs', []):
            vpc_id = vpc['VpcId']
            name = next((tag['Value'] for tag in vpc.get('Tags', []) if tag['Key'] == 'Name'), vpc_id)
            vpcs_data[vpc_id] = {
                'VpcId': vpc_id, 'Name': name, 'CidrBlock': vpc['CidrBlock'],
                'Environment': get_environment_from_name(name, vpc.get('Tags', [])),
                'Subnets': [], 'RouteTables': [], 'LoadBalancers': []
            }

        # Requires ec2:DescribeSubnets
        subnets_response = ec2_client.describe_subnets()
        for subnet in subnets_response.get('Subnets', []):
            if subnet['VpcId'] in vpcs_data:
                vpcs_data[subnet['VpcId']]['Subnets'].append({
                    'SubnetId': subnet['SubnetId'], 'CidrBlock': subnet['CidrBlock'],
                    'AvailabilityZone': subnet['AvailabilityZone']
                })

        # Requires ec2:DescribeRouteTables
        routes_response = ec2_client.describe_route_tables()
        for table in routes_response.get('RouteTables', []):
            if table['VpcId'] in vpcs_data:
                routes = [{'Destination': r.get('DestinationCidrBlock', 'N/A'),
                           'Target': r.get('GatewayId') or r.get('TransitGatewayId') or r.get('NatGatewayId') or 'N/A'}
                          for r in table.get('Routes', [])]
                vpcs_data[table['VpcId']]['RouteTables'].append({
                    'RouteTableId': table['RouteTableId'], 'Routes': routes
                })

        # Requires elasticloadbalancing:* permissions
        lbs_response = elbv2_client.describe_load_balancers()
        for lb in lbs_response.get('LoadBalancers', []):
            if lb['VpcId'] in vpcs_data:
                lb_arn = lb['LoadBalancerArn']
                
                listeners_response = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn)
                listeners_details = []
                for listener in listeners_response.get('Listeners', []):
                    target_groups = []
                    for action in listener.get('DefaultActions', []):
                        if action['Type'] == 'forward' and 'TargetGroupArn' in action:
                            tg_arn = action['TargetGroupArn']
                            tg_response = elbv2_client.describe_target_groups(TargetGroupArns=[tg_arn])
                            tg_name = tg_response['TargetGroups'][0]['TargetGroupName'] if tg_response['TargetGroups'] else 'N/A'
                            
                            targets = []
                            health_response = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)
                            for target_health in health_response.get('TargetHealthDescriptions', []):
                                targets.append({
                                    'Id': target_health['Target']['Id'],
                                    'Port': target_health['Target'].get('Port'),
                                    'Health': target_health['TargetHealth']['State']
                                })
                            target_groups.append({'Name': tg_name, 'Targets': targets})

                    listeners_details.append({
                        'Port': listener['Port'], 'Protocol': listener['Protocol'],
                        'TargetGroups': target_groups
                    })

                vpcs_data[lb['VpcId']]['LoadBalancers'].append({
                    'Name': lb['LoadBalancerName'], 'DNSName': lb['DNSName'],
                    'Type': lb['Type'], 'Listeners': listeners_details
                })
                
        return {'vpcs': list(vpcs_data.values())}
    except ClientError as e:
        if 'AccessDenied' in str(e):
            print("Access Denied for VPC/Networking services. Skipping VPC data collection.")
            return {'error': '(NO IAM ACCESS)', 'vpcs': []}
        else:
            print(f"An unexpected Boto3 error occurred in get_vpc_data: {e}")
            raise e