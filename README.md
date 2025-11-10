# Email Verification Lambda Function

AWS Lambda function for email verification workflow - Assignment 9 CSYE6225

## Overview

This Lambda function is triggered by SNS when a new user registers. It:
1. Generates a unique verification token
2. Stores the token in DynamoDB with a 2-minute TTL
3. Sends a verification email via SendGrid

## Architecture

```
User Registration → SNS Topic → Lambda Function → DynamoDB + SendGrid Email
```

## Project Structure

```
serverless-fork/
├── .github/
│   └── workflows/
│       ├── ci.yml              # CI pipeline for testing
│       └── deploy-lambda.yml   # Deployment to AWS Lambda
├── src/
│   └── lambda_function.py      # Main Lambda handler
├── tests/
│   └── test_lambda_function.py # Unit tests
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt            # Python dependencies
```

## Prerequisites

- Python 3.11
- AWS Account with appropriate permissions
- SendGrid account and API key
- AWS resources already created via Terraform:
  - SNS Topic: `csye6225-email-verification-{env}`
  - DynamoDB Table: `csye6225-email-verification-{env}`
  - Lambda Function: `csye6225-email-verification-{env}`
  - Secrets Manager: SendGrid API key

## Local Development

### 1. Clone Repository

```bash
git clone <your-serverless-fork-repo>
cd serverless-fork
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test class
pytest tests/test_lambda_function.py::TestLambdaHandler -v
```

## Environment Variables

The Lambda function requires these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DYNAMODB_TABLE_NAME` | DynamoDB table for tokens | `csye6225-email-verification-dev` |
| `SENDGRID_SECRET_NAME` | Secrets Manager secret name | `sendgrid-api-key` |
| `FROM_EMAIL` | Sender email address | `noreply@malavgajera.me` |
| `DOMAIN` | Domain for verification links | `dev.malavgajera.me` |
| `AWS_REGION` | AWS region | `us-east-1` |

## GitHub Secrets Configuration

Add these secrets to your GitHub repository:

### Required Secrets

```
AWS_ACCESS_KEY_ID_DEV       # Dev account access key
AWS_SECRET_ACCESS_KEY_DEV   # Dev account secret key
AWS_ACCESS_KEY_ID_DEMO      # Demo account access key
AWS_SECRET_ACCESS_KEY_DEMO  # Demo account secret key
AWS_REGION                  # AWS region (e.g., us-east-1)
```

## CI/CD Pipeline

### CI Workflow (`.github/workflows/ci.yml`)

Triggers on:
- Pull requests to `main`
- Push to `main`

Steps:
1. Checkout code
2. Set up Python 3.11
3. Install dependencies
4. Run unit tests with coverage
5. Verify 80%+ code coverage
6. Upload coverage reports

### Deployment Workflow (`.github/workflows/deploy-lambda.yml`)

Triggers on:
- Push to `main` branch
- Manual workflow dispatch

Steps:
1. **Deploy to Dev:**
   - Package Lambda function
   - Update Lambda code in dev account
   - Publish new version
2. **Deploy to Demo:**
   - Runs after dev deployment
   - Package and deploy to demo account
   - Publish new version

## Lambda Function Details

### Handler: `lambda_function.lambda_handler`

### Input Event Format (from SNS)

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "Sns": {
        "Message": "{\"email\": \"user@example.com\", \"username\": \"user123\"}"
      }
    }
  ]
}
```

### Success Response

```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Email verification initiated successfully\"}"
}
```

### Error Responses

```json
{
  "statusCode": 400,
  "body": "{\"error\": \"Email is required\"}"
}
```

```json
{
  "statusCode": 500,
  "body": "{\"error\": \"Failed to store verification token\"}"
}
```

## Testing

### Unit Test Coverage

- ✅ Token generation (uniqueness, format)
- ✅ DynamoDB storage (success, errors, TTL)
- ✅ Email sending (success, errors, custom domain)
- ✅ Lambda handler (success, failures, edge cases)
- ✅ Secrets Manager integration

### Running Tests

```bash
# All tests with verbose output
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=src --cov-report=html

# Specific test
pytest tests/test_lambda_function.py::TestGenerateVerificationToken -v

# View HTML coverage report
# Open htmlcov/index.html in browser
```

## Deployment

### Automatic Deployment

Push to `main` branch triggers automatic deployment to:
1. Dev environment (first)
2. Demo environment (after dev succeeds)

### Manual Deployment

```bash
# Using AWS CLI
# 1. Create deployment package
pip install -r requirements.txt -t package/
cp src/lambda_function.py package/
cd package
zip -r ../lambda-deployment.zip .
cd ..

# 2. Update Lambda function
aws lambda update-function-code \
  --function-name csye6225-email-verification-dev \
  --zip-file fileb://lambda-deployment.zip \
  --profile dev

# 3. Publish new version
aws lambda publish-version \
  --function-name csye6225-email-verification-dev \
  --description "Manual deployment" \
  --profile dev
```

## Monitoring and Debugging

### CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/csye6225-email-verification-dev \
  --follow \
  --profile dev

# View logs from specific time
aws logs tail /aws/lambda/csye6225-email-verification-dev \
  --since 1h \
  --profile dev
```

### Testing SNS Trigger

```bash
# Publish test message to SNS
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:csye6225-email-verification-dev \
  --message '{"email": "test@example.com", "username": "testuser"}' \
  --profile dev
```

### Verify DynamoDB Entry

```bash
# Check if token was stored
aws dynamodb get-item \
  --table-name csye6225-email-verification-dev \
  --key '{"email": {"S": "test@example.com"}}' \
  --profile dev
```

## Common Issues & Solutions

### Issue 1: Lambda can't access DynamoDB

**Solution:** Verify Lambda execution role has permissions:
```bash
aws iam get-role-policy \
  --role-name LambdaExecutionRole \
  --policy-name DynamoDBAccess \
  --profile dev
```

### Issue 2: SendGrid email not sending

**Check:**
1. API key is correct in Secrets Manager
2. Sender email is verified in SendGrid
3. Domain authentication (SPF, DKIM) is set up

### Issue 3: Import errors in Lambda

**Solution:** Ensure all dependencies are packaged:
```bash
pip install -r requirements.txt -t package/
```

## Security

- ✅ No hardcoded credentials
- ✅ SendGrid API key stored in AWS Secrets Manager
- ✅ Customer-managed KMS encryption for DynamoDB and SNS
- ✅ Least privilege IAM permissions
- ✅ 2-minute token TTL for security

## Performance

- **Cold start:** ~500-800ms
- **Warm execution:** ~100-200ms
- **Memory:** 256 MB (configurable)
- **Timeout:** 30 seconds

## License

This project is part of CSYE6225 Cloud Computing course at Northeastern University.

## Author

Malav Gajera  
Northeastern University  
CSYE6225 - Fall 2024

## Related Repositories

- **Webapp:** `webapp` repository (FastAPI application)
- **Infrastructure:** `aws-infra` repository (Terraform)
- **Serverless:** `serverless-fork` repository (Lambda - this repo)