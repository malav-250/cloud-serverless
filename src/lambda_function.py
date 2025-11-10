import json
import os
import boto3
import hashlib
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Initialize AWS clients (lazy initialization for testing)
dynamodb = None
secrets_client = None
sendgrid_api_key = None


def get_dynamodb_client():
    """Get or create DynamoDB client"""
    global dynamodb
    if dynamodb is None:
        dynamodb = boto3.resource('dynamodb')
    return dynamodb


def get_secrets_client():
    """Get or create Secrets Manager client"""
    global secrets_client
    if secrets_client is None:
        secrets_client = boto3.client('secretsmanager')
    return secrets_client


def get_sendgrid_api_key():
    """Retrieve SendGrid API key from AWS Secrets Manager"""
    global sendgrid_api_key
    if sendgrid_api_key is None:
        secret_name = os.environ.get('SENDGRID_API_KEY_SECRET_NAME', 'csye6225-sendgrid-key-demo')
        try:
            client = get_secrets_client()
            response = client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            sendgrid_api_key = secret_data.get('api_key')
        except ClientError as e:
            print(f"Error retrieving SendGrid API key: {e}")
            raise
    return sendgrid_api_key


def generate_verification_token(email):
    """
    Generate a unique verification token for the user
    
    Args:
        email (str): User's email address
        
    Returns:
        str: Hex-encoded verification token
    """
    timestamp = str(time.time())
    random_string = os.urandom(32).hex()
    token_input = f"{email}{timestamp}{random_string}"
    token = hashlib.sha256(token_input.encode()).hexdigest()
    return token


def store_token_in_dynamodb(email, token, ttl_minutes=2):
    """
    Store verification token in DynamoDB with TTL
    
    Args:
        email (str): User's email address
        token (str): Verification token
        ttl_minutes (int): Time-to-live in minutes (default: 2)
        
    Returns:
        bool: True if successful, False otherwise
    """
    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'csye6225-email-verification')
    
    try:
        db = get_dynamodb_client()
        table = db.Table(table_name)
        
        # Calculate TTL (2 minutes from now)
        ttl_timestamp = int(time.time()) + (ttl_minutes * 60)
        
        # Store token with TTL
        table.put_item(
            Item={
                'email': email,
                'token': token,
                'created_at': datetime.utcnow().isoformat(),
                'ttl': ttl_timestamp
            }
        )
        
        print(f"Token stored successfully for {email}")
        return True
        
    except ClientError as e:
        print(f"Error storing token in DynamoDB: {e}")
        return False


def send_verification_email(email, token):
    """
    Send verification email using SendGrid
    
    Args:
        email (str): User's email address
        token (str): Verification token
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Import SendGrid here to avoid issues in testing
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        # Get environment variables
        from_email = os.environ.get('FROM_EMAIL', 'noreply@malavgajera.me')
        domain = os.environ.get('DOMAIN', 'malavgajera.me')
        
        # Construct verification link
        verification_link = f"http://{domain}/v1/user/verify?email={email}&token={token}"
        
        # Create email message
        message = Mail(
            from_email=Email(from_email),
            to_emails=To(email),
            subject='Verify Your Email Address',
            html_content=f"""
            <html>
                <body>
                    <h2>Welcome to CSYE6225 Web Application!</h2>
                    <p>Please verify your email address by clicking the link below:</p>
                    <p><a href="{verification_link}">Verify Email Address</a></p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p>{verification_link}</p>
                    <p><strong>This link will expire in 2 minutes.</strong></p>
                    <p>If you did not create an account, please ignore this email.</p>
                </body>
            </html>
            """
        )
        
        # Send email
        sg = SendGridAPIClient(get_sendgrid_api_key())
        response = sg.send(message)
        
        print(f"Email sent successfully to {email}. Status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"Error sending email via SendGrid: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler function
    
    Args:
        event (dict): SNS event containing user registration data
        context: Lambda context object
        
    Returns:
        dict: Response with status code and message
    """
    print(f"Lambda function invoked with event: {json.dumps(event)}")
    
    try:
        # Parse SNS message
        for record in event['Records']:
            if record['EventSource'] != 'aws:sns':
                print(f"Skipping non-SNS record: {record['EventSource']}")
                continue
            
            # Extract message from SNS
            sns_message = record['Sns']['Message']
            print(f"SNS Message: {sns_message}")
            
            # Parse message JSON
            message_data = json.loads(sns_message)
            
            # Get email from either 'email' or 'username' field
            # (webapp might send email as username)
            email = message_data.get('email') or message_data.get('username')
            first_name = message_data.get('first_name', '')
            last_name = message_data.get('last_name', '')
            
            if not email:
                print("Error: No email provided in SNS message")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Email is required'})
                }
            
            print(f"Processing verification for: {email}")
            print(f"User: {first_name} {last_name}")
            
            # Generate verification token
            token = generate_verification_token(email)
            print(f"Generated token for {email}")
            
            # Store token in DynamoDB
            if not store_token_in_dynamodb(email, token):
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to store verification token'})
                }
            
            # Send verification email
            if not send_verification_email(email, token):
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to send verification email'})
                }
            
            print(f"Email verification process completed for {email}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Email verification initiated successfully'})
        }
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in SNS message'})
        }
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }