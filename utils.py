# utils.py
import os
import re
import json
import boto3
from botocore.config import Config

# Shared retry config for all collectors: 'adaptive' mode backs off automatically
# when it detects throttling, instead of letting a single ThrottlingException
# bubble up as an unhandled ClientError and take down the whole collection run.
BOTO_CONFIG = Config(retries={'max_attempts': 8, 'mode': 'adaptive'})


def get_client(service_name, **kwargs):
    """Returns a boto3 client pre-configured with adaptive retry/backoff.
    Collectors should use this instead of calling boto3.client() directly."""
    return boto3.client(service_name, config=BOTO_CONFIG, **kwargs)


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

DEFAULT_ENV = 'no-category'

# Aliases map many spellings onto ONE canonical environment name, so that
# 'stg' and 'staging' (or 'prd' and 'production') no longer produce two
# separate environment reports describing the same environment.
DEFAULT_ENV_ALIASES = {
    # production
    'prod': 'prod', 'prd': 'prod', 'production': 'prod', 'live': 'prod',
    # pre-production - deliberately its own environment so it does NOT get
    # swept into 'prod' and inflate the production inventory.
    'preprod': 'preprod', 'preproduction': 'preprod', 'preprd': 'preprod',
    # staging
    'staging': 'staging', 'stg': 'staging', 'stage': 'staging',
    # user acceptance
    'uat': 'uat',
    # qa
    'qa': 'qa', 'quality': 'qa',
    # test
    'test': 'test', 'tst': 'test', 'testing': 'test',
    # development
    'dev': 'dev', 'develop': 'dev', 'development': 'dev', 'devel': 'dev',
    # other common non-prod
    'sandbox': 'sandbox', 'sbx': 'sandbox',
    'demo': 'demo',
}

# When a name legitimately matches more than one environment (e.g.
# 'staging-test-db'), this order decides the winner - instead of the old
# behaviour where whichever keyword happened to sit earlier in the list won.
DEFAULT_ENV_PRIORITY = [
    'prod', 'preprod', 'staging', 'uat', 'qa', 'test', 'dev', 'sandbox', 'demo',
]

DEFAULT_ENV_TAG_KEYS = [
    'env', 'environment', 'deployment', 'stage', 'tier', 'lifecycle',
]


def _load_overrides():
    """Allows per-account tuning via Lambda environment variables, so the same
    code can be deployed against projects with different naming conventions
    without a code change.

      ENV_ALIASES_JSON  = {"blue":"prod","green":"staging"}   (merged in)
      ENV_TAG_KEYS      = env,environment,tier                (replaces list)
      ENV_PRIORITY      = prod,preprod,staging,dev            (replaces list)
    """
    aliases = dict(DEFAULT_ENV_ALIASES)
    raw_aliases = os.environ.get('ENV_ALIASES_JSON')
    if raw_aliases:
        try:
            for k, v in json.loads(raw_aliases).items():
                aliases[str(k).lower()] = str(v).lower()
        except Exception as e:
            print(f"WARN: could not parse ENV_ALIASES_JSON, using defaults: {e}")

    tag_keys = DEFAULT_ENV_TAG_KEYS
    raw_tag_keys = os.environ.get('ENV_TAG_KEYS')
    if raw_tag_keys:
        tag_keys = [t.strip().lower() for t in raw_tag_keys.split(',') if t.strip()]

    priority = DEFAULT_ENV_PRIORITY
    raw_priority = os.environ.get('ENV_PRIORITY')
    if raw_priority:
        priority = [t.strip().lower() for t in raw_priority.split(',') if t.strip()]

    return aliases, tag_keys, priority


ENV_ALIASES, ENV_TAG_KEYS, ENV_PRIORITY = _load_overrides()

# Set SKIP_TAG_LOOKUPS=true to disable the extra per-resource tag API calls
# (faster / fewer calls, but falls back to name-based guessing only).
SKIP_TAG_LOOKUPS = os.environ.get('SKIP_TAG_LOOKUPS', '').lower() in ('1', 'true', 'yes')

# Audit trail of every categorisation decision, used by the dry-run mode so you
# can eyeball how names/tags were interpreted before trusting a full report.
ENV_AUDIT = []


def _tokenize(text):
    """Splits a resource name into comparable whole tokens.

    Handles camelCase ('prodApiHandler' -> prod, api, handler) and strips
    trailing digits ('prod01' -> prod), so matching is on whole words rather
    than substrings. This is what stops 'producer-service' matching 'prod'
    and 'latest-logs' matching 'test'.
    """
    if not text:
        return []
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', str(text))
    raw = [t for t in re.split(r'[^A-Za-z0-9]+', s.lower()) if t]
    tokens = []
    for t in raw:
        stripped = re.sub(r'\d+$', '', t)
        tokens.append(stripped if stripped else t)
    return tokens


def _match_tokens(tokens):
    """Returns every canonical environment found in the token list.

    Adjacent tokens are joined and tested first (greedy), so 'pre-prod-db'
    matches 'preprod' rather than matching 'prod' and being mislabelled as
    production.
    """
    matches = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            pair = tokens[i] + tokens[i + 1]
            if pair in ENV_ALIASES:
                matches.append(ENV_ALIASES[pair])
                i += 2
                continue
        if tokens[i] in ENV_ALIASES:
            matches.append(ENV_ALIASES[tokens[i]])
        i += 1
    return matches


def _pick(matches):
    """Resolves multiple matches using the explicit priority order."""
    if not matches:
        return None
    for env in ENV_PRIORITY:
        if env in matches:
            return env
    return matches[0]


def _normalize_tags(tags):
    """Normalises the many tag shapes AWS APIs return into [(key, value)].

    Covers: [{'Key','Value'}] (EC2/RDS/SNS), [{'key','value'}] (ECS),
    and plain {'k': 'v'} dicts (API Gateway, Lambda, Cognito, SQS, EKS).
    """
    if not tags:
        return []
    items = []
    if isinstance(tags, dict):
        items = [(str(k), str(v)) for k, v in tags.items()]
    elif isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            key = tag.get('Key', tag.get('key'))
            value = tag.get('Value', tag.get('value'))
            if key is not None:
                items.append((str(key), str(value if value is not None else '')))
    return items


def get_environment_details(name, tags=None):
    """Determines a resource's environment, returning the decision and how it
    was reached. Tags always win over the name; the name is only a fallback."""
    # 1. Tags are authoritative when present.
    for key, value in _normalize_tags(tags):
        if key.lower() in ENV_TAG_KEYS:
            # Run the VALUE through the same alias/token logic, so a resource
            # tagged Environment=Production or Environment=Pre-Prod is
            # recognised instead of silently falling through to name-guessing
            # (which the previous exact-match version did).
            env = _pick(_match_tokens(_tokenize(value)))
            if env:
                return {'environment': env, 'source': f'tag:{key}={value}', 'ambiguous': False}

    # 2. Fall back to the resource name.
    matches = _match_tokens(_tokenize(name))
    env = _pick(matches)
    if env:
        distinct = set(matches)
        return {
            'environment': env,
            'source': 'name',
            'ambiguous': len(distinct) > 1,
            'all_matches': sorted(distinct) if len(distinct) > 1 else None,
        }

    return {'environment': DEFAULT_ENV, 'source': 'default', 'ambiguous': False}


def get_environment_from_name(name, tags=None):
    """Backwards-compatible wrapper used by all collectors."""
    details = get_environment_details(name, tags)
    ENV_AUDIT.append({
        'name': str(name),
        'environment': details['environment'],
        'source': details['source'],
        'ambiguous': details.get('ambiguous', False),
        'all_matches': details.get('all_matches'),
    })
    if details.get('ambiguous'):
        print(f"NOTE: '{name}' matched multiple environments {details.get('all_matches')}; "
              f"resolved to '{details['environment']}' by priority order.")
    return details['environment']


def safe_tags(fetch_fn, description):
    """Runs a per-resource tag lookup, swallowing failures.

    Tag APIs are separate permissions from the describe/list calls, so a role
    missing e.g. sqs:ListQueueTags should degrade to name-based detection for
    that resource rather than failing the whole collector.
    """
    if SKIP_TAG_LOOKUPS:
        return None
    try:
        return fetch_fn()
    except Exception as e:
        print(f"WARN: could not fetch tags for {description}: {e}")
        return None
