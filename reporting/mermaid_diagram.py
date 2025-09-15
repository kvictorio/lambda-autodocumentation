# reporting/mermaid_diagram.py

def to_node_id(name, prefix=""):
    """Creates a Mermaid-safe node ID from a resource name."""
    safe_name = name.replace('-', '_').replace('.', '_').replace('/', '_')
    return f"{prefix}_{safe_name}"

def generate_mermaid_diagram(env_name, env_data, all_resources, lambda_db_connections):
    """
    Generates a structured Mermaid.js flowchart diagram with subgraphs and inferred network connections.
    """
    entrypoint_nodes, processor_nodes, messaging_nodes, database_nodes = {}, {}, {}, {}
    connections = set()

    # --- 1. Collect and Define All Nodes, Grouped by Section ---
    for api in env_data.get('api_gateways', []):
        entrypoint_nodes[to_node_id(api['Name'], 'api')] = f'        {to_node_id(api["Name"], "api")}["fa:fa-server {api["Name"]}"]'
    for vpc in env_data.get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            entrypoint_nodes[to_node_id(lb['Name'], 'lb')] = f'        {to_node_id(lb["Name"], "lb")}["fa:fa-network-wired {lb["Name"]}"]'
    for instance in env_data.get('instances', []):
        processor_nodes[to_node_id(instance['Name'], 'ec2')] = f'        {to_node_id(instance["Name"], "ec2")}["fa:fa-desktop {instance["Name"]}"]'
    for cluster in env_data.get('ecs_clusters', []):
        for service in cluster.get('Services', []):
            processor_nodes[to_node_id(service['Name'], 'ecs')] = f'        {to_node_id(service["Name"], "ecs")}["fa:fa-box-open {service["Name"]}"]'
    for func in env_data.get('functions', []):
        processor_nodes[to_node_id(func['Name'], 'lambda')] = f'        {to_node_id(func["Name"], "lambda")}[/"fa:fa-bolt {func["Name"]}"/]'
    for queue in env_data.get('sqs_queues', []):
        messaging_nodes[to_node_id(queue['Name'], 'sqs')] = f'        {to_node_id(queue["Name"], "sqs")}>"fa:fa-exchange-alt {queue["Name"]}"]'
    for stream in env_data.get('kinesis_streams', []):
        messaging_nodes[to_node_id(stream['Name'], 'kinesis')] = f'        {to_node_id(stream["Name"], "kinesis")}>"fa:fa-exchange-alt {stream["Name"]}"]'
    for stream in env_data.get('firehose_streams', []):
        messaging_nodes[to_node_id(stream['Name'], 'firehose')] = f'        {to_node_id(stream["Name"], "firehose")}>"fa:fa-exchange-alt {stream["Name"]}"]'
    for db in env_data.get('rds_instances', []):
        database_nodes[to_node_id(db['Name'], 'rds')] = f'        {to_node_id(db["Name"], "rds")}[("fa:fa-database {db["Name"]}")]'
    for cluster in env_data.get('neptune_clusters', []):
        database_nodes[to_node_id(cluster['Name'], 'neptune')] = f'        {to_node_id(cluster["Name"], "neptune")}[("fa:fa-database {cluster["Name"]}")]'
    for table in env_data.get('dynamodb_tables', []):
        database_nodes[to_node_id(table['Name'], 'dynamo')] = f'        {to_node_id(table["Name"], "dynamo")}[("fa:fa-database {table["Name"]}")]'
    for cache in env_data.get('elasticache_clusters', []):
        database_nodes[to_node_id(cache['Name'], 'elasticache')] = f'        {to_node_id(cache["Name"], "elasticache")}[("fa:fa-database {cache["Name"]}")]'

    all_nodes = {**entrypoint_nodes, **processor_nodes, **messaging_nodes, **database_nodes}

    # --- 2. Define Connections Between Nodes ---
    instance_id_to_name = {i['InstanceId']: i['Name'] for i in all_resources.get('ec2', {}).get('instances', [])}
    for vpc in all_resources.get('vpc', {}).get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            if to_node_id(lb['Name'], 'lb') in all_nodes:
                for listener in lb.get('Listeners', []):
                    for tg in listener.get('TargetGroups', []):
                        for target in tg.get('Targets', []):
                            if instance_name := instance_id_to_name.get(target['Id']):
                                connections.add(f"    {to_node_id(lb['Name'], 'lb')} --> {to_node_id(instance_name, 'ec2')}")
    for api in env_data.get('api_gateways', []):
        for route in api.get('Routes', []):
            if 'Lambda:' in route['Target']:
                connections.add(f"    {to_node_id(api['Name'], 'api')} --> {to_node_id(route['Target'].split('`')[1], 'lambda')}")
    for conn in lambda_db_connections:
        if conn['from'] in all_nodes and conn['to'] in all_nodes:
            connections.add(f"    {conn['from']} --> {conn['to']}")
    dynamo_tables = {t['Name'] for t in env_data.get('dynamodb_tables', [])}
    sqs_queues = {q['Name'] for q in env_data.get('sqs_queues', [])}
    for func in env_data.get('functions', []):
        func_node_id = to_node_id(func['Name'], 'lambda')
        for _, value in func.get('EnvironmentVariables', {}).items():
            for table in dynamo_tables:
                if table in value: connections.add(f"    {func_node_id} --> {to_node_id(table, 'dynamo')}")
            for queue in sqs_queues:
                if queue in value: connections.add(f"    {func_node_id} --> {to_node_id(queue, 'sqs')}")
    event_source_mappings = all_resources.get('lambda', {}).get('event_source_mappings', [])
    env_function_names = {f['Name'] for f in env_data.get('functions', [])}
    for mapping in event_source_mappings:
        try:
            function_name = mapping['FunctionArn'].split(':')[-1]
            if function_name in env_function_names and ':sqs:' in mapping['EventSourceArn']:
                connections.add(f"    {to_node_id(mapping['EventSourceArn'].split(':')[-1], 'sqs')} --> {to_node_id(function_name, 'lambda')}")
        except (IndexError, KeyError): continue

    # --- 2b. Inferred Network Connections from Security Groups ---
    sg_to_resources = {}
    all_resources_flat = [
        *all_resources.get('ec2', {}).get('instances', []),
        *all_resources.get('rds', {}).get('instances', []),
        *all_resources.get('lambda', {}).get('functions', []),
    ]
    # Add other resources like Neptune, LBs if they need to be part of this logic
    for resource in all_resources_flat:
        resource_type_prefix = ''
        if 'InstanceId' in resource: resource_type_prefix = 'ec2'
        elif 'DBInstanceIdentifier' in resource: resource_type_prefix = 'rds'
        elif 'FunctionName' in resource: resource_type_prefix = 'lambda'
        
        node_id = to_node_id(resource['Name'], resource_type_prefix)
        sg_ids = resource.get('SecurityGroups', []) or resource.get('SecurityGroupIds', [])
        for sg_id in sg_ids:
            if sg_id not in sg_to_resources: sg_to_resources[sg_id] = []
            sg_to_resources[sg_id].append(node_id)
            
    for sg_details in all_resources.get('ec2', {}).get('security_groups', []):
        dest_sg_id = sg_details['GroupId']
        dest_nodes = [n for n in sg_to_resources.get(dest_sg_id, []) if n in all_nodes]
        if not dest_nodes: continue

        for rule in sg_details.get('InboundRules', []):
            for pair in rule.get('UserIdGroupPairs', []):
                if source_sg_id := pair.get('GroupId'):
                    source_nodes = [n for n in sg_to_resources.get(source_sg_id, []) if n in all_nodes]
                    for src in source_nodes:
                        for dest in dest_nodes:
                            if src != dest:
                                # Using a dotted arrow for inferred connections
                                connections.add(f"    {src} -.-> {dest}")

    # --- 3. Assemble the MMD file ---
    mmd = ["flowchart LR"]
    mmd.append(f'\nsubgraph "ENVIRONMENT: {env_name.upper()}"')
    mmd.append("    direction LR")
    if entrypoint_nodes:
        mmd.append("\n    subgraph EntryPoint")
        mmd.extend(sorted(entrypoint_nodes.values())); mmd.append("    end")
    if processor_nodes:
        mmd.append("\n    subgraph Processor")
        mmd.extend(sorted(processor_nodes.values())); mmd.append("    end")
    if messaging_nodes:
        mmd.append("\n    subgraph 'Messaging Queue'")
        mmd.extend(sorted(messaging_nodes.values())); mmd.append("    end")
    if database_nodes:
        mmd.append("\n    subgraph Databases")
        mmd.extend(sorted(database_nodes.values())); mmd.append("    end")
    if connections:
        mmd.append("\n    %% --- Connections ---")
        mmd.extend(sorted(list(connections)))
    mmd.append("end")

    # --- 4. Styling ---
    mmd.append("\n%% --- Styling ---")
    if entrypoint_nodes: mmd.append(f"style {','.join(entrypoint_nodes.keys())} fill:#2E7D32,stroke:#1B5E20,color:#FFFFFF")
    if processor_nodes: mmd.append(f"style {','.join(processor_nodes.keys())} fill:#1976D2,stroke:#0D47A1,color:#FFFFFF")
    if database_nodes: mmd.append(f"style {','.join(database_nodes.keys())} fill:#F57F17,stroke:#E65100,color:#FFFFFF")
    if messaging_nodes: mmd.append(f"style {','.join(messaging_nodes.keys())} fill:#6A1B9A,stroke:#4A148C,color:#FFFFFF")
    
    return "\n".join(mmd)