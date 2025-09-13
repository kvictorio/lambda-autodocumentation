# reporting/markdown_report.py

def parse_ip_permission(rule):
    """Parses a security group rule into its components for table formatting."""
    parsed_rules = []
    protocol = rule.get('IpProtocol', 'all').upper()
    if protocol == '-1': protocol = 'All'
    from_port = rule.get('FromPort', 'All')
    to_port = rule.get('ToPort', 'All')
    port_range = "All"
    if from_port != 'All':
        port_range = str(from_port) if from_port == to_port else f"{from_port}-{to_port}"
    sources = []
    for ip_range in rule.get('IpRanges', []): sources.append(f"`{ip_range['CidrIp']}`")
    for group in rule.get('UserIdGroupPairs', []): sources.append(f"Group: `{group['GroupId']}`")
    for prefix_list in rule.get('PrefixListIds', []): sources.append(f"Prefix List: `{prefix_list['PrefixListId']}`")
    if not sources: sources.append("N/A")

    for source in sources:
        parsed_rules.append({ 'protocol': protocol, 'port_range': port_range, 'source_dest': source })
    return parsed_rules

def generate_text_report(env_name, env_data, all_resources, sg_cross_reference):
    """
    Generates a structured Markdown report for a SINGLE environment,
    including a cross-reference for Security Group assignments.
    """
    report = [f"## ENVIRONMENT: `{env_name.upper()}`\n"]
    
    ec2_maps = all_resources.get('ec2', {})
    subnet_map = ec2_maps.get('subnet_map', {})
    sg_map = ec2_maps.get('sg_map', {})

    # --- VPCs and Networking Section ---
    report.append("\n### VPCs and Networking\n")
    if all_resources.get('vpc', {}).get('error'):
        report.append(f"_{all_resources['vpc']['error']}_")
    elif env_data.get('vpcs'):
        for vpc in sorted(env_data['vpcs'], key=lambda x: x['Name']):
            report.append(f"* **VPC: {vpc['Name']}** (`{vpc['VpcId']}`)")
            report.append(f"  * **CIDR:** `{vpc['CidrBlock']}`")
            if vpc.get('Subnets'):
                report.append("  * **Subnets:**")
                report.append("    | Subnet ID | Availability Zone | CIDR Block |")
                report.append("    | :--- | :--- | :--- |")
                for subnet in sorted(vpc['Subnets'], key=lambda x: x['SubnetId']):
                    report.append(f"    | `{subnet['SubnetId']}` | {subnet['AvailabilityZone']} | `{subnet['CidrBlock']}` |")
            if vpc.get('LoadBalancers'):
                report.append("  * **Load Balancers:**")
                for lb in sorted(vpc['LoadBalancers'], key=lambda x: x['Name']):
                    report.append(f"    * **{lb['Name']}** (Type: `{lb['Type']}`)")
                    report.append(f"      * DNS: `{lb['DNSName']}`")
                    report.append("      * **Configuration:**")
                    report.append("        | Listener (Port / Protocol) | Target Group | Target ID | Health Status |")
                    report.append("        | :--- | :--- | :--- | :--- |")
                    for listener in lb['Listeners']:
                        listener_text = f"`{listener['Port']}` ({listener['Protocol']})"
                        if not listener['TargetGroups']:
                             report.append(f"        | {listener_text} | *No Target Group* | | |")
                        else:
                            for i, tg in enumerate(listener['TargetGroups']):
                                tg_to_show = tg['Name'] if i == 0 else ""
                                if not tg['Targets']:
                                    report.append(f"        | {listener_text if i == 0 else ''} | {tg_to_show} | *No Targets Registered* | |")
                                else:
                                    for j, target in enumerate(tg['Targets']):
                                        report.append(f"        | {listener_text if i == 0 and j == 0 else ''} | {tg_to_show if j == 0 else ''} | `{target['Id']}` | {target['Health']} |")
            if vpc.get('RouteTables'):
                report.append("  * **Route Tables:**")
                for table in vpc['RouteTables']:
                    report.append(f"    * **Table ID:** `{table['RouteTableId']}`")
                    report.append("      | Destination | Target |"); report.append("      | :--- | :--- |")
                    for route in table['Routes']:
                        report.append(f"      | `{route['Destination']}` | `{route['Target']}` |")
    else:
        report.append("_No VPC resources found in this environment._")

    # --- EC2 Instances Section ---
    report.append("\n### EC2 Instances\n")
    if all_resources.get('ec2', {}).get('error'):
        report.append(f"_{all_resources['ec2']['error']}_")
    elif env_data.get('instances'):
        report.append("| Instance Name | Instance ID | Subnet | Security Groups |")
        report.append("| :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['instances'], key=lambda x: x['Name']):
            subnet_name = subnet_map.get(item.get('SubnetId'), item.get('SubnetId', 'N/A'))
            sg_names = [sg_map.get(sg_id, sg_id) for sg_id in item.get('SecurityGroups', [])]
            report.append(f"| **{item['Name']}** | `{item['InstanceId']}` | {subnet_name} | {', '.join(sg_names)} |")
    else:
        report.append("_No EC2 Instances found in this environment._")

 # --- Container Services Section ---
    report.append("\n### Container Services (ECR, EKS, ECS)\n")
    if all_resources.get('container', {}).get('error'):
        report.append(f"_{all_resources['container']['error']}_")
    else:
        # ECR
        if env_data.get('ecr_repositories'):
            report.append("#### Elastic Container Registry (ECR)\n")
            report.append("| Repository Name | URI |")
            report.append("| :--- | :--- |")
            for item in sorted(env_data['ecr_repositories'], key=lambda x: x['Name']):
                report.append(f"| {item['Name']} | `{item['URI']}` |")
        
        # EKS
        if env_data.get('eks_clusters'):
            report.append("\n#### Elastic Kubernetes Service (EKS)\n")
            report.append("| Cluster Name | K8s Version | Status |")
            report.append("| :--- | :--- | :--- |")
            for item in sorted(env_data['eks_clusters'], key=lambda x: x['Name']):
                report.append(f"| **{item['Name']}** | `{item['Version']}` | {item['Status']} |")

        # ECS
        if env_data.get('ecs_clusters'):
            report.append("\n#### Elastic Container Service (ECS)\n")
            for cluster in sorted(env_data['ecs_clusters'], key=lambda x: x['Name']):
                report.append(f"* **Cluster: {cluster['Name']}** (Status: `{cluster['Status']}`)")
                if cluster.get('Services'):
                    report.append("  * **Services:**")
                    report.append("    | Service Name | Status | Launch Type | Desired Tasks |")
                    report.append("    | :--- | :--- | :--- | :--- |")
                    for service in sorted(cluster['Services'], key=lambda x: x['Name']):
                        report.append(f"    | {service['Name']} | {service['Status']} | `{service['LaunchType']}` | {service['DesiredCount']} |")

    # --- Relational Databases (RDS) Section ---
    report.append("\n### Relational Databases (RDS)\n")
    if all_resources.get('rds', {}).get('error'):
        report.append(f"_{all_resources['rds']['error']}_")
    elif env_data.get('rds_instances'):
        report.append("| Instance Name | Engine | Size | Endpoint | Subnets | Security Groups |")
        report.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['rds_instances'], key=lambda x: x['Name']):
            subnets = ", ".join([subnet_map.get(s_id, s_id) for s_id in item['SubnetIds']])
            sgs = ", ".join([sg_map.get(sg_id, sg_id) for sg_id in item['SecurityGroupIds']])
            report.append(f"| **{item['Name']}** | {item['Engine']} | `{item['InstanceClass']}` | `{item['Endpoint']}` | {subnets} | {sgs} |")
    else:
        report.append("_No RDS Instances found in this environment._")

    # --- Neptune Section ---
    report.append("\n### Graph Databases (Neptune)\n")
    if all_resources.get('neptune', {}).get('error'):
        report.append(f"_{all_resources['neptune']['error']}_")
    elif env_data.get('neptune_clusters'):
        for cluster in sorted(env_data['neptune_clusters'], key=lambda x: x['Name']):
            report.append(f"* **Cluster: {cluster['Name']}** (Engine: `{cluster['Engine']}`, Status: `{cluster['Status']}`)")
            report.append(f"  * **Writer Endpoint:** `{cluster['Endpoint']}`")
            report.append(f"  * **Reader Endpoint:** `{cluster['ReaderEndpoint']}`")
            if cluster.get('Instances'):
                report.append("  * **Instances:**")
                report.append("    | Instance Name | Size | Role | Subnets | Security Groups |")
                report.append("    | :--- | :--- | :--- | :--- | :--- |")
                for inst in sorted(cluster['Instances'], key=lambda x: x['Name']):
                    role = "Writer" if inst['IsClusterWriter'] else "Reader"
                    subnets = ", ".join([subnet_map.get(s_id, s_id) for s_id in inst['SubnetIds']])
                    sgs = ", ".join([sg_map.get(sg_id, sg_id) for sg_id in inst['SecurityGroupIds']])
                    report.append(f"    | `{inst['Name']}` | `{inst['InstanceClass']}` | {role} | {subnets} | {sgs} |")
    else:
        report.append("_No Neptune Clusters found in this environment._")
    
    # --- DynamoDB Section ---
    report.append("\n### NoSQL Databases (DynamoDB)\n")
    if all_resources.get('dynamodb', {}).get('error'):
        report.append(f"_{all_resources['dynamodb']['error']}_")
    elif env_data.get('dynamodb_tables'):
        report.append("| Table Name | Status | Item Count | Size (MB) | Billing Mode | Primary Key |")
        report.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['dynamodb_tables'], key=lambda x: x['Name']):
            report.append(f"| **{item['Name']}** | {item['Status']} | {item['ItemCount']:,} | {item['TableSizeMB']} | {item['BillingMode']} | `{item['PrimaryKey']}` |")
    else:
        report.append("_No DynamoDB Tables found in this environment._")

    # --- Elasticache Section ---
    report.append("\n### In-Memory Cache (ElastiCache)\n")
    if all_resources.get('elasticache', {}).get('error'):
        report.append(f"_{all_resources['elasticache']['error']}_")
    elif env_data.get('elasticache_clusters'):
        report.append("| Cluster Name | Engine | Node Type | Status | Endpoint |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['elasticache_clusters'], key=lambda x: x['Name']):
            report.append(f"| **{item['Name']}** | {item['Engine']} | `{item['NodeType']}` | {item['Status']} | `{item['Endpoint']}` |")
    else:
        report.append("_No ElastiCache Clusters found in this environment._")

    # --- API Gateways Section ---
    report.append("\n### API Gateways\n")
    if all_resources.get('apigateway', {}).get('error'):
        report.append(f"_{all_resources['apigateway']['error']}_")
    elif env_data.get('api_gateways'):
        for item in sorted(env_data['api_gateways'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['ApiId']}`, Type: `{item['ProtocolType']}`)")
            if item.get('Routes'):
                report.append("  * **Routes:**")
                report.append("    | Route / Path | Authorizer | Integration Target |")
                report.append("    | :--- | :--- | :--- |")
                for route in item['Routes']:
                    report.append(f"    | `{route['RouteKey']}` | {route['Authorizer']} | {route['Target']} |")
    else:
        report.append("_No API Gateways found in this environment._")

    # --- Lambda Functions Section ---
    report.append("\n### Lambda Functions\n")
    if all_resources.get('lambda', {}).get('error'):
        report.append(f"_{all_resources['lambda']['error']}_")
    elif env_data.get('functions'):
        report.append("| Function Name | Runtime | VPC Connected | Subnets | Security Groups |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['functions'], key=lambda x: x['Name']):
            if item.get('VpcId'):
                vpc_connected = "Yes"
                subnet_names = [subnet_map.get(s_id, s_id) for s_id in item.get('SubnetIds', [])]
                sg_names = [sg_map.get(sg_id, sg_id) for sg_id in item.get('SecurityGroupIds', [])]
            else:
                vpc_connected = "No"; subnet_names = ["N/A"]; sg_names = ["N/A"]
            report.append(f"| **{item['Name']}** | `{item.get('Runtime', 'N/A')}` | {vpc_connected} | {', '.join(subnet_names)} | {', '.join(sg_names)} |")
    else:
        report.append("_No Lambda Functions found in this environment._")

    # --- S3 Buckets Section ---
    report.append("\n### S3 Buckets\n")
    if all_resources.get('s3', {}).get('error'):
        report.append(f"_{all_resources['s3']['error']}_")
    elif env_data.get('s3_buckets'):
        for item in sorted(env_data['s3_buckets'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}**")
    else:
        report.append("_No S3 Buckets found in this environment._")
    
    # --- Security Group Rules Section ---
    report.append("\n### Security Group Rules\n")
    if all_resources.get('ec2', {}).get('error'):
        report.append(f"_{all_resources['ec2']['error']}_")
    elif env_data.get('security_groups'):
        report.append("| Security Group | Assigned To | Direction | Protocol | Port Range | Source / Destination |")
        report.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['security_groups'], key=lambda x: x['Name']):
            sg_name_full = f"**{item['Name']}** (`{item['GroupId']}`)"
            
            assignments = sg_cross_reference.get(item['GroupId'], ["_Not in use_"])
            assignments_str = "<br>".join(assignments)

            is_first_rule_for_group = True
            all_rules = []
            for rule in item.get('InboundRules', []):
                for parsed in parse_ip_permission(rule): all_rules.append({'direction': 'Inbound', **parsed})
            if not item.get('InboundRules'): all_rules.append({'direction': 'Inbound', 'protocol': 'N/A', 'port_range': 'N/A', 'source_dest': 'No rules defined'})
            for rule in item.get('OutboundRules', []):
                for parsed in parse_ip_permission(rule): all_rules.append({'direction': 'Outbound', **parsed})
            if not item.get('OutboundRules'): all_rules.append({'direction': 'Outbound', 'protocol': 'N/A', 'port_range': 'N/A', 'source_dest': 'No rules defined'})
            
            for i, rule in enumerate(all_rules):
                sg_name_to_display = sg_name_full if i == 0 else ""
                assignments_to_display = assignments_str if i == 0 else ""
                report.append(f"| {sg_name_to_display} | {assignments_to_display} | {rule['direction']} | {rule['protocol']} | {rule['port_range']} | {rule['source_dest']} |")
    else:
        report.append("_No Security Groups found in this environment._")
    
    # --- Cognito Section ---
    report.append("\n### Identity (Cognito)\n")
    if all_resources.get('cognito', {}).get('error'):
        report.append(f"_{all_resources['cognito']['error']}_")
    elif env_data.get('user_pools'):
        for pool in sorted(env_data['user_pools'], key=lambda x: x['Name']):
            report.append(f"* **User Pool: {pool['Name']}** (`{pool['Id']}`)")
            if pool.get('AppClients'):
                for client in pool['AppClients']:
                    report.append(f"  * **App Client:** {client['ClientName']} (`{client['ClientId']}`)")
    else:
        report.append("_No Cognito User Pools found in this environment._")

    # --- Queues and Streams Sections  ---
    report.append("\n### Queues & Streams (SQS, Kinesis)\n")
    if all_resources.get('queues', {}).get('error'):
        report.append(f"_{all_resources['queues']['error']}_")
    else:
        # SQS Queues
        if env_data.get('sqs_queues'):
            report.append("#### Simple Queue Service (SQS)\n")
            report.append("| Queue Name | Type | Approx. Messages |")
            report.append("| :--- | :--- | :--- |")
            for item in sorted(env_data['sqs_queues'], key=lambda x: x['Name']):
                report.append(f"| **{item['Name']}** | {item['Type']} | {item['MessageCount']} |")
        
        # Kinesis Data Streams
        if env_data.get('kinesis_streams'):
            report.append("\n#### Kinesis Data Streams\n")
            report.append("| Stream Name | Status | Shard Count |")
            report.append("| :--- | :--- | :--- |")
            for item in sorted(env_data['kinesis_streams'], key=lambda x: x['Name']):
                report.append(f"| **{item['Name']}** | {item['Status']} | {item['Shards']} |")

        # Kinesis Firehose
        if env_data.get('firehose_streams'):
            report.append("\n#### Kinesis Data Firehose\n")
            report.append("| Delivery Stream Name | Status | Destination |")
            report.append("| :--- | :--- | :--- |")
            for item in sorted(env_data['firehose_streams'], key=lambda x: x['Name']):
                report.append(f"| **{item['Name']}** | {item['Status']} | {item['Destination']} |")

    return "\n".join(report)