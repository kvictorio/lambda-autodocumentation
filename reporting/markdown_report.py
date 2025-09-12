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
    
    # If a rule has multiple sources, create a row for each
    if sources:
        for source in sources:
            parsed_rules.append({
                'protocol': protocol,
                'port_range': port_range,
                'source_dest': source
            })
    else: # For rules with no specific source (like all traffic)
        parsed_rules.append({
            'protocol': protocol,
            'port_range': port_range,
            'source_dest': 'N/A'
        })

    return parsed_rules

def generate_text_report(env_name, env_data):
    """Generates a structured Markdown report for a SINGLE environment."""
    report = [f"## ENVIRONMENT: `{env_name.upper()}`\n"]

    # --- EC2 Instances Section ---
    if env_data.get('instances'):
        report.append("\n### EC2 Instances\n")
        for item in sorted(env_data['instances'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['InstanceId']}`)")

    # --- Security Groups Section ---
    if env_data.get('security_groups'):
        report.append("\n### Security Groups\n")
        for item in sorted(env_data['security_groups'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['GroupId']}`)")
            
            if item.get('InboundRules'):
                report.append("  * **Inbound Rules:**")
                report.append("    | Protocol | Port Range | Source |")
                report.append("    | :--- | :--- | :--- |")
                for rule in item['InboundRules']:
                    parsed_list = parse_ip_permission(rule)
                    for parsed in parsed_list:
                        report.append(f"    | {parsed['protocol']} | {parsed['port_range']} | {parsed['source_dest']} |")
            
            if item.get('OutboundRules'):
                report.append("  * **Outbound Rules:**")
                report.append("    | Protocol | Port Range | Destination |")
                report.append("    | :--- | :--- | :--- |")
                for rule in item['OutboundRules']:
                    parsed_list = parse_ip_permission(rule)
                    for parsed in parsed_list:
                        report.append(f"    | {parsed['protocol']} | {parsed['port_range']} | {parsed['source_dest']} |")

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
                    for listener in lb['Listeners']:
                        report.append(f"      * Listener: Port `{listener['Port']}` ({listener['Protocol']})")

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
        for item in sorted(env_data['functions'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (Runtime: `{item.get('Runtime', 'N/A')}`)")

    # --- S3 Buckets Section ---
    if env_data.get('s3_buckets'):
        report.append("\n### S3 Buckets\n")
        for item in sorted(env_data['s3_buckets'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}**")

    return "\n".join(report)