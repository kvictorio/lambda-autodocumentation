# reporting/html_report.py

def generate_text_report(env_name, env_data, ec2_maps):
    """Generates a structured HTML report for a SINGLE environment."""
    
    # --- HTML & CSS Boilerplate ---
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Report: {env_name.upper()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 2em; background-color: #f7f7f7; }}
        h1, h2, h3 {{ color: #111; }}
        table {{ border-collapse: collapse; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #232f3e; color: #ffffff; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        tr:hover {{ background-color: #ddd; }}
        code {{ background-color: #eee; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
        .sg-name {{ font-weight: bold; }}
    </style>
</head>
<body>
    <h1>AWS Infrastructure Report</h1>
    <h2>ENVIRONMENT: <code>{env_name.upper()}</code></h2>
"""

    # --- Security Group Section ---
    if env_data.get('security_groups'):
        html += "<h3>Security Group Rules</h3>"
        html += """
        <table>
            <thead>
                <tr>
                    <th>Security Group</th>
                    <th>Direction</th>
                    <th>Protocol</th>
                    <th>Port Range</th>
                    <th>Source / Destination</th>
                </tr>
            </thead>
            <tbody>
        """
        for sg in sorted(env_data['security_groups'], key=lambda x: x['Name']):
            inbound_rules = sg.get('InboundRules', [])
            outbound_rules = sg.get('OutboundRules', [])
            
            # Calculate rowspan for the SG name cell
            total_rules = max(1, len(inbound_rules)) + max(1, len(outbound_rules))

            # --- RENDER INBOUND RULES ---
            if inbound_rules:
                for i, rule in enumerate(inbound_rules):
                    html += "<tr>"
                    if i == 0: # Only print the SG name cell for the first row
                        html += f'<td class="sg-name" rowspan="{total_rules}">{sg["Name"]}<br><code>{sg["GroupId"]}</code></td>'
                    
                    parsed = parse_ip_permission(rule)[0] # Assuming one source per rule for simplicity here
                    html += f"<td>Inbound</td><td>{parsed['protocol']}</td><td>{parsed['port_range']}</td><td>{parsed['source_dest']}</td>"
                    html += "</tr>"
            else:
                html += "<tr>"
                html += f'<td class="sg-name" rowspan="{total_rules}">{sg["Name"]}<br><code>{sg["GroupId"]}</code></td>'
                html += "<td>Inbound</td><td colspan='3' style='text-align:center;'>No rules defined</td>"
                html += "</tr>"
                
            # --- RENDER OUTBOUND RULES ---
            if outbound_rules:
                for i, rule in enumerate(outbound_rules):
                    html += "<tr>"
                    if i == 0 and not inbound_rules: # Only print SG name if there were no inbound rules
                         html += f'<td class="sg-name" rowspan="{total_rules}">{sg["Name"]}<br><code>{sg["GroupId"]}</code></td>'

                    parsed = parse_ip_permission(rule)[0]
                    html += f"<td>Outbound</td><td>{parsed['protocol']}</td><td>{parsed['port_range']}</td><td>{parsed['source_dest']}</td>"
                    html += "</tr>"
            else:
                html += "<tr>"
                if not inbound_rules:
                    html += f'<td class="sg-name" rowspan="{total_rules}">{sg["Name"]}<br><code>{sg["GroupId"]}</code></td>'
                html += "<td>Outbound</td><td colspan='3' style='text-align:center;'>No rules defined</td>"
                html += "</tr>"
                
        html += "</tbody></table>"

    # --- We can add other sections (EC2, etc.) here later ---

    # --- Close HTML Document ---
    html += "</body></html>"
    return html

def parse_ip_permission(rule):
    # This helper function is still useful, but simplified for this example
    protocol = rule.get('IpProtocol', 'all').upper()
    if protocol == '-1': protocol = 'All'
    from_port = rule.get('FromPort', 'All')
    to_port = rule.get('ToPort', 'All')
    port_range = "All"
    if from_port != 'All':
        port_range = str(from_port) if from_port == to_port else f"{from_port}-{to_port}"
    sources = [f"<code>{ip['CidrIp']}</code>" for ip in rule.get('IpRanges', [])]
    if not sources: sources.append("N/A")
    
    return [{'protocol': protocol, 'port_range': port_range, 'source_dest': ', '.join(sources)}]