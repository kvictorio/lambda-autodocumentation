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


