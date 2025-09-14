# reporting/mermaid_diagram.py

def to_node_id(name, prefix=""):
    """Creates a Mermaid-safe node ID from a resource name."""
    safe_name = name.replace('-', '_').replace('.', '_').replace('/', '_')
    return f"{prefix}_{safe_name}"

def generate_mermaid_diagram(env_name, env_data, all_resources, lambda_db_connections):
    """
    Generates a structured Mermaid.js flowchart diagram with subgraphs for each architectural tier.
    """
    # Dictionaries to hold nodes for each column
    entrypoint_nodes = {}
    processor_nodes = {}
    messaging_nodes = {}
    database_nodes = {}
    
    connections = set()

    # --- 1. Collect and Define All Nodes, Grouped by Section ---

    # EntryPoint: API Gateways & Load Balancers
    for api in env_data.get('api_gateways', []):
        node_id = to_node_id(api['Name'], 'api')
        entrypoint_nodes[node_id] = f'        {node_id}["fa:fa-server {api["Name"]}"]'
    for vpc in env_data.get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            node_id = to_node_id(lb['Name'], 'lb')
            entrypoint_nodes[node_id] = f'        {node_id}["fa:fa-network-wired {lb["Name"]}"]'

    # Processor: EC2, ECS Services, Lambda
    for instance in env_data.get('instances', []):
        node_id = to_node_id(instance['Name'], 'ec2')
        processor_nodes[node_id] = f'        {node_id}["fa:fa-desktop {instance["Name"]}"]'
    for cluster in env_data.get('ecs_clusters', []):
        for service in cluster.get('Services', []):
            node_id = to_node_id(service['Name'], 'ecs')
            processor_nodes[node_id] = f'        {node_id}["fa:fa-box-open {service["Name"]}"]'
    for func in env_data.get('functions', []):
        node_id = to_node_id(func['Name'], 'lambda')
        processor_nodes[node_id] = f'        {node_id}[/"fa:fa-bolt {func["Name"]}"/]'

    # Messaging Queue: SQS, Kinesis
    for queue in env_data.get('sqs_queues', []):
        node_id = to_node_id(queue['Name'], 'sqs')
        messaging_nodes[node_id] = f'        {node_id}>"fa:fa-exchange-alt {queue["Name"]}"]'
    for stream in env_data.get('kinesis_streams', []):
        node_id = to_node_id(stream['Name'], 'kinesis')
        messaging_nodes[node_id] = f'        {node_id}>"fa:fa-exchange-alt {stream["Name"]}"]'
    for stream in env_data.get('firehose_streams', []):
        node_id = to_node_id(stream['Name'], 'firehose')
        messaging_nodes[node_id] = f'        {node_id}>"fa:fa-exchange-alt {stream["Name"]}"]'

    # Databases: RDS, Neptune, DynamoDB, ElastiCache
    for db in env_data.get('rds_instances', []):
        node_id = to_node_id(db['Name'], 'rds')
        database_nodes[node_id] = f'        {node_id}[("fa:fa-database {db["Name"]}")]'
    for cluster in env_data.get('neptune_clusters', []):
        node_id = to_node_id(cluster['Name'], 'neptune')
        database_nodes[node_id] = f'        {node_id}[("fa:fa-database {cluster["Name"]}")]'
    for table in env_data.get('dynamodb_tables', []):
        node_id = to_node_id(table['Name'], 'dynamo')
        database_nodes[node_id] = f'        {node_id}[("fa:fa-database {table["Name"]}")]'
    for cache in env_data.get('elasticache_clusters', []):
        node_id = to_node_id(cache['Name'], 'elasticache')
        database_nodes[node_id] = f'        {node_id}[("fa:fa-database {cache["Name"]}")]'

    # Combine all node IDs for connection logic
    all_nodes = {**entrypoint_nodes, **processor_nodes, **messaging_nodes, **database_nodes}

    # --- 2. Define Connections Between Nodes ---
    # This logic remains the same, as it connects nodes regardless of their subgraph
    instance_id_to_name = {i['InstanceId']: i['Name'] for i in env_data.get('instances', [])}
    for vpc in env_data.get('vpcs', []):
        for lb in vpc.get('LoadBalancers', []):
            lb_node_id = to_node_id(lb['Name'], 'lb')
            for listener in lb.get('Listeners', []):
                for tg in listener.get('TargetGroups', []):
                    for target in tg.get('Targets', []):
                        if instance_name := instance_id_to_name.get(target['Id']):
                            connections.add(f"    {lb_node_id} --> {to_node_id(instance_name, 'ec2')}")
    for api in env_data.get('api_gateways', []):
        api_node_id = to_node_id(api['Name'], 'api')
        for route in api.get('Routes', []):
            if 'Lambda:' in route['Target']:
                func_name = route['Target'].split('`')[1]
                connections.add(f"    {api_node_id} --> {to_node_id(func_name, 'lambda')}")
    for conn in lambda_db_connections:
        if conn['from'] in all_nodes and conn['to'] in all_nodes:
            connections.add(f"    {conn['from']} --> {conn['to']}")
    dynamo_tables = {t['Name'] for t in env_data.get('dynamodb_tables', [])}
    sqs_queues = {q['Name'] for q in env_data.get('sqs_queues', [])}
    kinesis_streams = {s['Name'] for s in env_data.get('kinesis_streams', [])}
    for func in env_data.get('functions', []):
        func_node_id = to_node_id(func['Name'], 'lambda')
        for _, value in func.get('EnvironmentVariables', {}).items():
            for table in dynamo_tables:
                if table in value: connections.add(f"    {func_node_id} --> {to_node_id(table, 'dynamo')}")
            for queue in sqs_queues:
                if queue in value: connections.add(f"    {func_node_id} --> {to_node_id(queue, 'sqs')}")
            for stream in kinesis_streams:
                if stream in value: connections.add(f"    {func_node_id} --> {to_node_id(stream, 'kinesis')}")
    event_source_mappings = all_resources.get('lambda', {}).get('event_source_mappings', [])
    env_function_names = {f['Name'] for f in env_data.get('functions', [])}
    for mapping in event_source_mappings:
        try:
            function_name = mapping['FunctionArn'].split(':')[-1]
            if function_name in env_function_names:
                source_arn = mapping['EventSourceArn']
                if ':sqs:' in source_arn:
                    connections.add(f"    {to_node_id(source_arn.split(':')[-1], 'sqs')} --> {to_node_id(function_name, 'lambda')}")
                elif ':kinesis:' in source_arn:
                    connections.add(f"    {to_node_id(source_arn.split('/')[-1], 'kinesis')} --> {to_node_id(function_name, 'lambda')}")
        except (IndexError, KeyError): continue

    # --- 3. Assemble the MMD file with Subgraphs ---
    mmd = ["flowchart LR"]
    mmd.append(f'\nsubgraph "ENVIRONMENT: {env_name.upper()}"')
    mmd.append("    direction LR")

    if entrypoint_nodes:
        mmd.append("\n    subgraph EntryPoint")
        mmd.append("        direction LR")
        mmd.extend(sorted(entrypoint_nodes.values()))
        mmd.append("    end")
    if processor_nodes:
        mmd.append("\n    subgraph Processor")
        mmd.append("        direction LR")
        mmd.extend(sorted(processor_nodes.values()))
        mmd.append("    end")
    if messaging_nodes:
        mmd.append("\n    subgraph 'Messaging Queue'")
        mmd.append("        direction LR")
        mmd.extend(sorted(messaging_nodes.values()))
        mmd.append("    end")
    if database_nodes:
        mmd.append("\n    subgraph Databases")
        mmd.append("        direction LR")
        mmd.extend(sorted(database_nodes.values()))
        mmd.append("    end")

    if connections:
        mmd.append("\n    %% --- Connections ---")
        mmd.extend(sorted(list(connections)))

    mmd.append("end")

    # --- 4. Styling Section ---
    mmd.append("\n%% --- Styling ---")
    if entrypoint_nodes:
        mmd.append(f"style {','.join(entrypoint_nodes.keys())} fill:#2E7D32,stroke:#1B5E20,color:#FFFFFF")
    if processor_nodes:
        mmd.append(f"style {','.join(processor_nodes.keys())} fill:#1976D2,stroke:#0D47A1,color:#FFFFFF")
    if database_nodes:
        mmd.append(f"style {','.join(database_nodes.keys())} fill:#F57F17,stroke:#E65100,color:#FFFFFF")
    if messaging_nodes:
        mmd.append(f"style {','.join(messaging_nodes.keys())} fill:#6A1B9A,stroke:#4A148C,color:#FFFFFF")
    
    return "\n".join(mmd)