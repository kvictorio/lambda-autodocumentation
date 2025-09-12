# reporting/markdown_report.py

def parse_ip_permission(rule):
    """Parses a security group rule into its components for table formatting."""
    parsed_rules = []
    protocol = rule.get('IpProtocol', 'all').upper()
    if protocol == '-1':
        protocol = 'All'

    from_port = rule.get('FromPort', 'All')
    to_port = rule.get('ToPort', 'All')
    
    port_range = "All"
    if from_port != 'All':
        port_range = str(from_port) if from_port == to_port else f"{from_port}-{to_port}"

    # Get all sources/destinations
    sources = []
    for ip_range in rule.get('IpRanges', []):
        sources.append(f"`{ip_range['CidrIp']}`")
    for group in rule.get('UserIdGroupPairs', []):
        sources.append(f"Group: `{group['GroupId']}`")
    for prefix_list in rule.get('PrefixListIds', []):
        sources.append(f"Prefix List: `{prefix_list['PrefixListId']}`")
    
    if sources:
        for source in sources:
            parsed_rules.append({
                'protocol': protocol,
                'port_range': port_range,
                'source_dest': source
            })
    else:
        parsed_rules.append({
            'protocol': protocol,
            'port_range': port_range,
            'source_dest': 'N/A'
        })

    return parsed_rules

def generate_text_report(env_name, env_data, ec2_maps):
    """Generates a structured Markdown report for a SINGLE environment."""
    report = [f"## ENVIRONMENT: `{env_name.upper()}`\n"]
    
    subnet_map = ec2_maps.get('subnet_map', {})
    sg_map = ec2_maps.get('sg_map', {})

    # --- EC2 Instances Section ---
    if env_data.get('instances'):
        report.append("\n### EC2 Instances\n")
        report.append("| Instance Name | Instance ID | Subnet | Security Groups |")
        report.append("| :--- | :--- | :--- | :--- |")
        for item in sorted(env_data['instances'], key=lambda x: x['Name']):
            instance_name = item['Name']
            instance_id = f"`{item['InstanceId']}`"
            
            # Look up the subnet name, fall back to ID if not found
            subnet_name = subnet_map.get(item.get('SubnetId'), item.get('SubnetId', 'N/A'))
            
            # Look up security group names, fall back to ID
            sg_names = [sg_map.get(sg_id, sg_id) for sg_id in item.get('SecurityGroups', [])]
            sg_list = ", ".join(sg_names)
            
            report.append(f"| **{instance_name}** | {instance_id} | {subnet_name} | {sg_list} |")

    # --- Security Groups Section ---
    if env_data.get('security_groups'):
        report.append("\n### Security Group Rules\n")
        report.append("| Security Group | Direction | Protocol | Port Range | Source / Destination |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        
        for item in sorted(env_data['security_groups'], key=lambda x: x['Name']):
            sg_name = f"**{item['Name']}** (`{item['GroupId']}`)"
            
            # Process Inbound Rules
            if not item.get('InboundRules'):
                 report.append(f"| {sg_name} | Inbound | N/A | N/A | No rules defined |")
            else:
                for rule in item['InboundRules']:
                    parsed_list = parse_ip_permission(rule)
                    for i, parsed in enumerate(parsed_list):
                        # Show the SG name only on the first row for that group's rules
                        current_sg_name = sg_name if i == 0 else ""
                        report.append(f"| {current_sg_name} | Inbound | {parsed['protocol']} | {parsed['port_range']} | {parsed['source_dest']} |")

            # Process Outbound Rules
            if not item.get('OutboundRules'):
                report.append(f"| {sg_name} | Outbound | N/A | N/A | No rules defined |")
            else:
                for rule in item['OutboundRules']:
                    parsed_list = parse_ip_permission(rule)
                    for i, parsed in enumerate(parsed_list):
                        # If there were no inbound rules, the SG name needs to be printed here on the first outbound row
                        current_sg_name = sg_name if not item.get('InboundRules') and i == 0 else ""
                        report.append(f"| {current_sg_name} | Outbound | {parsed['protocol']} | {parsed['port_range']} | {parsed['source_dest']} |")

    # --- VPCs and Networking Section ---
    if env_data.get('vpcs'):
        report.append("\n### VPCs and Networking\n")
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
                    
                    # Create Listener/Target table
                    report.append("      * **Configuration:**")
                    report.append("        | Listener (Port / Protocol) | Target Group | Target ID | Health Status |")
                    report.append("        | :--- | :--- | :--- | :--- |")
                    for listener in lb['Listeners']:
                        listener_text = f"`{listener['Port']}` ({listener['Protocol']})"
                        if not listener['TargetGroups']:
                             report.append(f"        | {listener_text} | *No Target Group* | | |")
                        else:
                            for i, tg in enumerate(listener['TargetGroups']):
                                listener_to_show = listener_text if i == 0 else ""
                                if not tg['Targets']:
                                    report.append(f"        | {listener_to_show} | {tg['Name']} | *No Targets Registered* | |")
                                else:
                                    for j, target in enumerate(tg['Targets']):
                                        listener_and_tg_to_show = listener_text if j == 0 else ""
                                        tg_to_show = tg['Name'] if j == 0 else ""
                                        report.append(f"        | {listener_and_tg_to_show} | {tg_to_show} | `{target['Id']}` | {target['Health']} |")

            if vpc.get('RouteTables'):
                report.append("  * **Route Tables:**")
                for table in vpc['RouteTables']:
                    report.append(f"    * **Table ID:** `{table['RouteTableId']}`")
                    report.append("      | Destination | Target |")
                    report.append("      | :--- | :--- |")
                    for route in table['Routes']:
                        report.append(f"      | `{route['Destination']}` | `{route['Target']}` |")

    # --- API Gateways Section ---
    if env_data.get('api_gateways'):
        report.append("\n### API Gateways\n")
        for item in sorted(env_data['api_gateways'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['ApiId']}`, Type: `{item['ProtocolType']}`)")
            if item.get('Routes'):
                report.append(f"  * **Routes:** {len(item['Routes'])}")
            if item.get('Authorizers'):
                report.append(f"  * **Authorizers:** {', '.join(item['Authorizers'])}")

    # --- Lambda Functions Section ---
    if env_data.get('functions'):
        report.append("\n### Lambda Functions\n")
        report.append("| Function Name | Runtime | VPC Connected | Subnets | Security Groups |")
        report.append("| :--- | :--- | :--- | :--- | :--- |")
        
        for item in sorted(env_data['functions'], key=lambda x: x['Name']):
            name = f"**{item['Name']}**"
            runtime = f"`{item.get('Runtime', 'N/A')}`"
            
            if item.get('VpcId'):
                vpc_connected = "Yes"
                # Look up subnet and security group names
                subnet_names = [subnet_map.get(s_id, s_id) for s_id in item.get('SubnetIds', [])]
                sg_names = [sg_map.get(sg_id, sg_id) for sg_id in item.get('SecurityGroupIds', [])]
                subnets_list = ", ".join(subnet_names)
                sgs_list = ", ".join(sg_names)
            else:
                vpc_connected = "No"
                subnets_list = "N/A"
                sgs_list = "N/A"
            
            report.append(f"| {name} | {runtime} | {vpc_connected} | {subnets_list} | {sgs_list} |")
    # --- S3 Buckets Section ---
    if env_data.get('s3_buckets'):
        report.append("\n### S3 Buckets\n")
        for item in sorted(env_data['s3_buckets'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}**")

    return "\n".join(report)