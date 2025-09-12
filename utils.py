# utils.py

# Keywords to identify environments from resource names/tags
ENV_KEYWORDS = ['prod', 'dev', 'test', 'uat', 'qa', 'staging']

def get_environment_from_name(name, tags=None):
    """Parses a resource name or its tags to find an environment keyword."""
    search_string = name.lower()
    if tags:
        for tag in tags:
            search_string += tag['Key'].lower() + tag['Value'].lower()

    for env in ENV_KEYWORDS:
        if env in search_string:
            return env
    return "no-category"