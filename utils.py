# utils.py

# Define the keywords and tags to look for. Using lists makes it easy to add more aliases.
ENV_KEYWORDS = ['prod', 'dev', 'test', 'uat', 'qa', 'staging', 'stg']
ENV_TAG_KEYS = ['env', 'environment', 'deployment']

def get_environment_from_name(name, tags=None):
    """
    Determines the environment of a resource by first checking for specific tags,
    then falling back to parsing the resource name.
    """
    # 1. Prioritize checking tags for a definitive environment assignment
    if tags:
        # The 'tags' parameter can be a list of dicts or a single dict. Normalize it.
        tag_items = []
        if isinstance(tags, list):
            # Standard format for EC2, RDS, etc. -> [{'Key': 'k', 'Value': 'v'}]
            tag_items = tags
        elif isinstance(tags, dict):
            # Format for API Gateway -> {'k': 'v'}
            tag_items = [{'Key': k, 'Value': v} for k, v in tags.items()]

        for tag in tag_items:
            # Check for a matching tag key (case-insensitive)
            tag_key = tag.get('Key', '').lower()
            if tag_key in ENV_TAG_KEYS:
                # If the key matches, check if the value is a known environment (case-insensitive)
                tag_value = tag.get('Value', '').lower()
                if tag_value in ENV_KEYWORDS:
                    return tag_value # Return the matched environment from the tag value

    # 2. Fallback to checking the resource name if no matching tag was found
    search_string = name.lower()
    for env in ENV_KEYWORDS:
        if env in search_string:
            return env

    # 3. Default if no environment is found by either method
    return "no-category"