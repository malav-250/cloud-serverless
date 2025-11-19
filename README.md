## Prerequisites for Local Development

### Required Software
- **Python 3.11** ([Download](https://www.python.org/downloads/)) 
- **AWS CLI** configured with profiles ([Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- **Git** for version control

### AWS Resources (Must exist before deployment)
The following resources must be created via Terraform first:
- Lambda Function: `csye6225-email-verification-{env}`
- SNS Topic: `csye6225-email-verification-{env}`
- DynamoDB Table: `email-verification-tokens-{env}`
- Secrets Manager: SendGrid API key stored as `csye6225-sendgrid-key-{env}`

### AWS Profile Configuration

**`~/.aws/credentials`:**
```ini
[dev]
aws_access_key_id = YOUR_DEV_ACCESS_KEY
aws_secret_access_key = YOUR_DEV_SECRET_KEY

[demo]
aws_access_key_id = YOUR_DEMO_ACCESS_KEY
aws_secret_access_key = YOUR_DEMO_SECRET_KEY
```

**`~/.aws/config`:**
```ini
[profile dev]
region = us-east-1
output = json

[profile demo]
region = us-east-1
output = json
```

**Verify:**
```bash
aws sts get-caller-identity --profile dev
aws sts get-caller-identity --profile demo
```

## Build and Deploy Instructions

### 1. Local Setup

```bash
# Clone repository
git clone <your-serverless-repo-url>
cd serverless

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

### 3. Build Deployment Package

```bash
# Install Lambda-compatible dependencies
pip install --platform manylinux2014_x86_64 \
  --target package \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --upgrade \
  -r requirements.txt

# Copy Lambda function code
cp src/lambda_function.py package/

# Create deployment zip
cd package
zip -r ../lambda-deployment.zip .
cd ..
```

### 4. Deploy to AWS

**Deploy to Dev:**
```bash
# Set AWS profile
export AWS_PROFILE=dev  # Linux/Mac
$env:AWS_PROFILE="dev"  # Windows PowerShell

# Update Lambda function code
aws lambda update-function-code \
  --function-name csye6225-email-verification-dev \
  --zip-file fileb://lambda-deployment.zip \
  --region us-east-1

# Wait for update to complete
aws lambda wait function-updated \
  --function-name csye6225-email-verification-dev \
  --region us-east-1

# Update environment variables
aws lambda update-function-configuration \
  --function-name csye6225-email-verification-dev \
  --environment Variables="{DOMAIN=dev.malavgajera.me,FROM_EMAIL=noreply@malavgajera.me,SENDGRID_API_KEY_SECRET_NAME=csye6225-sendgrid-key-dev,DYNAMODB_TABLE_NAME=email-verification-tokens-dev}" \
  --region us-east-1

# Publish new version
aws lambda publish-version \
  --function-name csye6225-email-verification-dev \
  --description "Manual deployment" \
  --region us-east-1
```

**Deploy to Demo:**
```bash
# Set AWS profile
export AWS_PROFILE=demo  # Linux/Mac
$env:AWS_PROFILE="demo"  # Windows PowerShell

# Update Lambda function code
aws lambda update-function-code \
  --function-name csye6225-email-verification-demo \
  --zip-file fileb://lambda-deployment.zip \
  --region us-east-1

# Wait for update to complete
aws lambda wait function-updated \
  --function-name csye6225-email-verification-demo \
  --region us-east-1

# Update environment variables
aws lambda update-function-configuration \
  --function-name csye6225-email-verification-demo \
  --environment Variables="{DOMAIN=demo.malavgajera.me,FROM_EMAIL=noreply@malavgajera.me,SENDGRID_API_KEY_SECRET_NAME=csye6225-sendgrid-key-demo,DYNAMODB_TABLE_NAME=email-verification-tokens-demo}" \
  --region us-east-1

# Publish new version
aws lambda publish-version \
  --function-name csye6225-email-verification-demo \
  --description "Manual deployment" \
  --region us-east-1
```

### 5. Verify Deployment

```bash
# Check Lambda function exists
aws lambda get-function \
  --function-name csye6225-email-verification-dev \
  --region us-east-1

# View CloudWatch logs
aws logs tail /aws/lambda/csye6225-email-verification-dev \
  --follow \
  --region us-east-1

# Test by publishing to SNS (replace with your topic ARN)
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:043310666846:csye6225-email-verification-dev \
  --message '{"email":"test@example.com","first_name":"Test","token":"test-token-123","token_expiry":"2024-01-01T00:00:00Z"}' \
  --region us-east-1
```

## Automated Deployment via CI/CD

**Preferred Method:** Use GitHub Actions instead of manual deployment.

1. Push code to `main` branch
2. GitHub Actions automatically:
   - Runs tests
   - Builds deployment package
   - Deploys to dev environment
   - Deploys to demo environment (after dev succeeds)

**GitHub Secrets Required:**
- `AWS_ACCESS_KEY_ID_DEV`
- `AWS_SECRET_ACCESS_KEY_DEV`
- `AWS_ACCESS_KEY_ID_DEMO`
- `AWS_SECRET_ACCESS_KEY_DEMO`
- `AWS_REGION`