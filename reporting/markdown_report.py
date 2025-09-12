# reporting/markdown_report.py

# Helper function to parse security group rules
def format_ip_permission(rule):
    # ... (code for format_ip_permission remains the same)
    formatted_rules = []
    protocol = rule.get('IpProtocol', 'all').upper()
    if protocol == '-1': protocol = 'All'
    from_port, to_port = rule.get('FromPort', 'All'), rule.get('ToPort', 'All')
    port_range = f"port {from_port}" if from_port == to_port else f"ports {from_port}-{to_port}"
    if str(from_port) == 'All': port_range = "all ports"
    sources = []
    for ip_range in rule.get('IpRanges', []): sources.append(f"`{ip_range['CidrIp']}`")
    for group in rule.get('UserIdGroupPairs', []): sources.append(f"group `{group['GroupId']}`")
    for prefix_list in rule.get('PrefixListIds', []): sources.append(f"prefix list `{prefix_list['PrefixListId']}`")
    if sources: formatted_rules.append(f"Allows {port_range} ({protocol}) from {', '.join(sources)}")
    return formatted_rules

def generate_text_report(env_name, env_data):
    """Generates a structured Markdown report for a SINGLE environment."""
    # ... (code for generate_text_report remains the same)
    report = [f"## ENVIRONMENT: `{env_name.upper()}`\n"]
    if env_data.get('s3_buckets'):
        report.append("### S3 Buckets\n")
        for item in sorted(env_data['s3_buckets'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}**")
    if env_data.get('instances'):
        report.append("\n### EC2 Instances\n")
        for item in sorted(env_data['instances'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['InstanceId']}`)")
    if env_data.get('security_groups'):
        report.append("\n### Security Groups\n")
        for item in sorted(env_data['security_groups'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (`{item['GroupId']}`)")
            if item.get('InboundRules'):
                report.append("  * **Inbound Rules:**")
                for rule in item['InboundRules']:
                    for r in format_ip_permission(rule): report.append(f"    * {r}")
            if item.get('OutboundRules'):
                report.append("  * **Outbound Rules:**")
                for rule in item['OutboundRules']:
                    for r in format_ip_permission(rule): report.append(f"    * {r}")
    if env_data.get('functions'):
        report.append("\n### Lambda Functions\n")
        for item in sorted(env_data['functions'], key=lambda x: x['Name']):
            report.append(f"* **{item['Name']}** (Runtime: `{item.get('Runtime', 'N/A')}`)")
    return "\n".join(report)