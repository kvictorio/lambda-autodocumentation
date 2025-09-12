# AWS Document Generator

aws document generator uses AWS Lambda fucntion to collect data from your infrastructure and create a html document for you

It segregates them into seperate files per environment, DEV, QA, TEST, UAT, STAGING, PROD
You'll have to indicate the environmental variable for the S3 Bucket it will be placed on in lambda

**S3_BUCKET_NAME** = \<name of your s3 bucket>

Then you'll need a read olicy to allow your lambda to access the resources and write to your S3 bucket.


```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeRouteTables",
                "lambda:ListFunctions",
                "lambda:GetFunctionConfiguration",
                "lambda:GetPolicy",
                "s3:ListAllMyBuckets",
                "s3:GetBucketTagging",
                "s3:GetBucketLocation",
                "apigateway:GET",
                "apigatewayv2:Get*",
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeListeners",
                "elasticloadbalancing:DescribeTargetGroups"
            ],
            "Resource": "*"
        },
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

Thankyou!


