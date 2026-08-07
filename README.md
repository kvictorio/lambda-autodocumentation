# AWS Document Generator

aws document generator uses AWS Lambda fucntion to collect data from your infrastructure and create a **markdown** document and **mermaid** diagram for you

It segregates them into seperate files per environment, DEV, QA, TEST, UAT, STAGING, PROD
The segration is either via the naming convention or the resource tagging.

* Runtime = **Python 3.12**

#### 1. You'll have to indicate the environmental variable for the S3 Bucket it will be placed on in lambda

* **S3_BUCKET_NAME** = \<name of your s3 bucket>

#### 2. Then you'll need a read policy to allow your lambda to access the resources and write to your S3 bucket.


```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::<s3-bucketname>/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

#### 3. Then add the AWS ReadOnlyAccess policy to your lambda role for the lambda to have access to list down the neccesary information for your document

Thankyou!



---

## Environment detection

Resources are grouped by environment using **tags first, resource name second**.

Tag keys checked (case-insensitive): `env`, `environment`, `deployment`, `stage`, `tier`, `lifecycle`.
Tag values and names are matched on **whole tokens**, so `producer-service` is no longer
mistaken for `prod`. Aliases are canonicalised (`stg`/`stage` → `staging`, `prd`/`production` → `prod`),
and `preprod` / `pre-prod` resolve to their own `preprod` environment rather than being
swept into production.

### Optional environment variables

| Variable | Purpose |
| :--- | :--- |
| `S3_BUCKET_NAME` | **Required.** Destination bucket for reports. |
| `DRY_RUN` | `true` = write only the detection review sheet, no reports. |
| `ENV_ALIASES_JSON` | Extra name→environment aliases, e.g. `{"blue":"prod","green":"staging"}` |
| `ENV_TAG_KEYS` | Comma-separated override of which tag keys mean "environment". |
| `ENV_PRIORITY` | Comma-separated tie-break order when a name matches several. |
| `SKIP_TAG_LOOKUPS` | `true` = skip per-resource tag API calls (faster, less accurate). |

### Validate before you trust it

Run once with `DRY_RUN=true` (or invoke with the test event `{"dry_run": true}`).
This writes `DRY-RUN-environment-detection.md` listing every resource, the environment
assigned, and whether it came from a tag or a guessed name — review it, then run for real.

### Additional IAM permissions

Accurate detection needs the tag-read actions, which are separate from the describe/list
actions. These are all included in the AWS-managed `ReadOnlyAccess` policy. If you use a
tighter custom policy, add: `lambda:ListTags`, `dynamodb:ListTagsOfResource`,
`cognito-idp:DescribeUserPool`, `sns:ListTagsForResource`, `events:ListTagsForResource`,
`elasticache:ListTagsForResource`, `sqs:ListQueueTags`, `kinesis:ListTagsForStream`,
`firehose:ListTagsForDeliveryStream`, `ecr:ListTagsForResource`, `ecs:DescribeClusters`,
`iam:ListRoleTags`, `iam:ListUserTags`.

Missing any one of these degrades that resource to name-based detection with a warning —
it does not fail the run.
