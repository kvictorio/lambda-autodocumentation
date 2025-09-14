# reporting/mermaid_diagram.py

def generate_mermaid_diagram(env_name, env_data, all_resources, lambda_db_connections):
    """
    Generates an architecture diagram with connections and nested grouping.
    """
    mermaid_script = ["graph LR;"] # LR = Left to Right

    # --- Style Definitions ---
    mermaid_script.append("\n  %% --- Style Definitions ---")
    mermaid_script.append("  classDef ec2Style fill:#FF9900,stroke:#333,stroke-width:2px;")
    mermaid_script.append("  classDef lambdaStyle fill:#7D3F98,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef sgStyle fill:#D12C2C,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef apiStyle fill:#3B48CC,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef lbStyle fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef tgStyle fill:#8BC34A,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef rdsStyle fill:#0075B8,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef ddbStyle fill:#4D8CFE,stroke:#333,stroke-width:2px,color:#fff;")
    mermaid_script.append("  classDef ecsStyle fill:#F58536,stroke:#333,stroke-width:2px,color:#fff;")

    # --- Main Environment Subgraph Starts Here ---
    mermaid_script.append(f'\n  subgraph ENVIRONMENT: {env_name.upper()}')
    mermaid_script.append("    direction LR;")

    # --- Nested Subgraphs for Node Definitions ---
    
    mermaid_script.append("\n    subgraph Entrypoints")
    for item in env_data.get('api_gateways', []):
        node_id = "api_" + item['ApiId'].replace('-', '_')
        mermaid_script.append(f"      {node_id}{{{'API: ' + item['Name']}}}:::apiStyle;")
    for vpc in env_data.get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            lb_node_id = "lb_" + lb['Name'].replace('-', '_').replace('.', '_')
            mermaid_script.append(f"      {lb_node_id}[\"LB: {lb['Name']}\"]:::lbStyle;")
    mermaid_script.append("    end")
    
    mermaid_script.append("\n    subgraph Application & Compute")
    for item in env_data.get('instances', []):
        node_id = item['InstanceId'].replace('-', '')
        mermaid_script.append(f"      {node_id}[\"EC2: {item['Name']}\"]:::ec2Style;")
    for item in env_data.get('functions', []):
        node_id = "lambda_" + item['Name'].replace('-', '_').replace('.', '_')
        mermaid_script.append(f"      {node_id}[\"fa:fa-bolt Lambda: {item['Name']}\"]:::lambdaStyle;")
    for item in env_data.get('ecs_clusters', []):
         for service in item.get('Services', []):
            node_id = "ecs_" + service['Name'].replace('-', '_')
            mermaid_script.append(f"      {node_id}[\"ECS Service: {service['Name']}\"]:::ecsStyle;")
    mermaid_script.append("    end")
    
    mermaid_script.append("\n    subgraph Databases & Cache")
    for item in env_data.get('rds_instances', []):
        node_id = "rds_" + item['Name'].replace('-', '_')
        mermaid_script.append(f"      {node_id}[(\"RDS: {item['Name']}\")]:::rdsStyle;")
    for item in env_data.get('dynamodb_tables', []):
        node_id = "ddb_" + item['Name'].replace('-', '_')
        mermaid_script.append(f"      {node_id}[(\"DDB: {item['Name']}\")]:::ddbStyle;")
    for item in env_data.get('neptune_clusters', []):
        node_id = "neptune_" + item['Name'].replace('-', '_')
        mermaid_script.append(f"      {node_id}[(\"Neptune: {item['Name']}\")]:::rdsStyle;")
    for item in env_data.get('elasticache_clusters', []):
        node_id = "elasticache_" + item['Name'].replace('-', '_')
        mermaid_script.append(f"      {node_id}[(\"ElastiCache: {item['Name']}\")]:::rdsStyle;")
    mermaid_script.append("    end")

    # Define all necessary Security Group nodes INSIDE the main subgraph
    all_sgs_map = {sg['GroupId']: sg['Name'] for sg in all_resources['ec2'].get('security_groups', [])}
    sg_nodes_to_define = set()
    resources_with_sgs = env_data.get('instances', []) + env_data.get('rds_instances', []) + env_data.get('functions', [])
    for resource in resources_with_sgs:
        resource_id_safe = (resource.get('InstanceId') or resource.get('Name')).replace('-', '').replace('.', '_')
        for sg_id in resource.get('SecurityGroups', []) or resource.get('SecurityGroupIds', []):
            sg_name = all_sgs_map.get(sg_id, sg_id)
            sg_node_id = f"sg_{resource_id_safe}_{sg_id.replace('-', '')}"
            sg_nodes_to_define.add(f"    {sg_node_id}[\"SG: {sg_name}\"]:::sgStyle;")
    
    if sg_nodes_to_define:
        mermaid_script.append("\n    subgraph Security")
        for node_def in sorted(list(sg_nodes_to_define)):
            mermaid_script.append(f"      {node_def}")
        mermaid_script.append("    end")

    # Connection Definitions (still inside the main subgraph)
    mermaid_script.append("\n    %% --- Connections ---")
    
    for api in env_data.get('api_gateways', []):
        api_node_id = "api_" + api['ApiId'].replace('-', '_')
        for route in api.get('Routes', []):
            if 'Lambda:' in route['Target']:
                lambda_name = route['Target'].split('`')[1]
                lambda_node_id = "lambda_" + lambda_name.replace('-', '_').replace('.', '_')
                mermaid_script.append(f'    {api_node_id} -->|"{route["RouteKey"]}"| {lambda_node_id};')

    for vpc in env_data.get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            lb_node_id = "lb_" + lb['Name'].replace('-', '_').replace('.', '_')
            for listener in lb.get('Listeners', []):
                for tg in listener.get('TargetGroups', []):
                    tg_node_id = "tg_" + tg['Name'].replace('-', '_').replace('.', '_')
                    mermaid_script.append(f"    {lb_node_id} -->|Port {listener['Port']}| {tg_node_id};")
                    for target in tg.get('Targets', []):
                        target_id_clean = target['Id'].replace('-', '')
                        mermaid_script.append(f"    {tg_node_id} --> {target_id_clean};")
    
    for conn in lambda_db_connections:
        lambda_exists = any(f['Name'].replace('-', '_').replace('.', '_') in conn['from'] for f in env_data.get('functions', []))
        db_exists = False
        db_resource_types = ['rds_instances', 'neptune_clusters', 'elasticache_clusters']
        for resource_type in db_resource_types:
            if any(db['Name'].replace('-', '_') in conn['to'] for db in env_data.get(resource_type, [])):
                db_exists = True
                break
        if lambda_exists and db_exists:
            mermaid_script.append(f"    {conn['from']} ==>|Uses Env Var: {conn['label']}| {conn['to']};")

    for inst in env_data.get('instances', []):
        inst_node_id = inst['InstanceId'].replace('-', '')
        for sg_id in inst.get('SecurityGroups', []):
            sg_node_id = f"sg_{inst_node_id}_{sg_id.replace('-', '')}"
            mermaid_script.append(f"    {inst_node_id} -.-> {sg_node_id};")

    for rds in env_data.get('rds_instances', []):
        rds_node_id = "rds_" + rds['Name'].replace('-', '_')
        for sg_id in rds.get('SecurityGroupIds', []):
            sg_node_id = f"sg_{rds_node_id}_{sg_id.replace('-', '')}"
            mermaid_script.append(f"    {rds_node_id} -.-> {sg_node_id};")

    for func in env_data.get('functions', []):
        if func.get('SecurityGroupIds'):
            func_node_id = "lambda_" + func['Name'].replace('-', '_').replace('.', '_')
            for sg_id in func.get('SecurityGroupIds', []):
                func_id_safe = func_node_id.replace('.', '_')
                sg_node_id = f"sg_{func_id_safe}_{sg_id.replace('-', '')}"
                mermaid_script.append(f"    {func_node_id} -.-> {sg_node_id};")

    # --- Main Environment Subgraph Ends Here ---
    mermaid_script.append("  end")

    return "\n".join(mermaid_script)