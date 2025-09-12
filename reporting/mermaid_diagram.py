# reporting/mermaid_diagram.py

# reporting/mermaid_diagram.py

def generate_mermaid_diagram(env_name, env_data, all_sgs):
    """Generates an architecture diagram for a SINGLE environment."""
    mermaid_script = ["graph LR;"]

    mermaid_script.append("\n  %% --- Style Definitions ---")
    mermaid_script.append("  classDef ec2Style fill:#FF9900,stroke:#333,stroke-width:2px;")
    mermaid_script.append("  classDef lambdaStyle fill:#7D3F98,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef s3Style fill:#5A92B3,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef sgStyle fill:#D12C2C,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef apiStyle fill:#3B48CC,stroke:#333,stroke-width:2px,color:#fff;") # <-- ADD THIS STYLE

    mermaid_script.append(f"\n  subgraph {env_name.upper()}")
    
    for item in env_data.get('api_gateways', []): # <-- ADD THIS BLOCK
        node_id = item['ApiId'].replace('-', '_')
        mermaid_script.append(f"    {node_id}{{{'API: ' + item['Name']}}}:::apiStyle;")
    for item in env_data.get('s3_buckets', []):
        node_id = item['Name'].replace('-', '_').replace('.', '_')
        mermaid_script.append(f"    {node_id}[(\"S3: {item['Name']}\")]:::s3Style;")
    for item in env_data.get('instances', []):
        node_id = item['InstanceId'].replace('-', '')
        mermaid_script.append(f"    {node_id}[\"EC2: {item['Name']}\"]:::ec2Style;")
    for item in env_data.get('functions', []):
        node_id = item['Name'].replace('-', '_').replace('.', '_')
        mermaid_script.append(f"    {node_id}[\"fa:fa-bolt Lambda: {item['Name']}\"]:::lambdaStyle;")
    mermaid_script.append("  end")
    mermaid_script.append("\n  %% --- Connections ---")
    connections_exist = False
    for inst in env_data.get('instances', []):
        inst_node_id = inst['InstanceId'].replace('-', '')
        for sg_id in inst['SecurityGroups']:
            sg_obj = next((sg for sg in all_sgs if sg['GroupId'] == sg_id), None)
            if sg_obj:
                if not connections_exist:
                    mermaid_script.append(f"  subgraph Security")
                    connections_exist = True
                sg_node_id = sg_id.replace('-', '')
                mermaid_script.append(f"    {sg_node_id}[\"SG: {sg_obj['Name']}\"]:::sgStyle;")
                mermaid_script.append(f"  {inst_node_id} --> {sg_node_id};")
    if connections_exist:
        mermaid_script.append(f"  end")
    return "\n".join(mermaid_script)