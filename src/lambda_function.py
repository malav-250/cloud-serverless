import json
import os
import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize AWS clients
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


def check_email_already_sent(email, token):
    """
    Check if email was already sent for this token
    
    Args:
        email (str): User's email address
        token (str): Verification token
        
    Returns:
        bool: True if email was already sent, False otherwise
    """
    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'email-verification-tokens-demo')
    
    try:
        db = get_dynamodb_client()
        table = db.Table(table_name)
        
        # Check if this email+token combination exists
        response = table.get_item(
            Key={'email': email}
        )
        
        if 'Item' in response:
            stored_token = response['Item'].get('token')
            email_sent = response['Item'].get('email_sent', False)
            
            # If same token and email already sent, return True (duplicate)
            if stored_token == token and email_sent:
                print(f"Email already sent for {email} with token {token}")
                return True
        
        return False
        
    except ClientError as e:
        print(f"Error checking DynamoDB: {e}")
        # In case of error, assume not sent (fail open for better UX)
        return False


def store_email_sent_record(email, token, ttl_minutes=2):
    """
    Store record that email was sent for this token
    
    Args:
        email (str): User's email address
        token (str): Verification token
        ttl_minutes (int): Time-to-live in minutes (default: 2)
        
    Returns:
        bool: True if successful, False otherwise
    """
    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'email-verification-tokens-demo')
    
    try:
        db = get_dynamodb_client()
        table = db.Table(table_name)
        
        # Calculate TTL (2 minutes from now)
        ttl_timestamp = int(time.time()) + (ttl_minutes * 60)
        
        # Store record
        table.put_item(
            Item={
                'email': email,
                'token': token,
                'email_sent': True,
                'sent_at': datetime.utcnow().isoformat(),
                'ttl': ttl_timestamp
            }
        )
        
        print(f"Email sent record stored for {email}")
        return True
        
    except ClientError as e:
        print(f"Error storing email record in DynamoDB: {e}")
        return False


def send_verification_email(email, token, first_name):
    """
    Send verification email using SendGrid
    
    Args:
        email (str): User's email address
        token (str): Verification token
        first_name (str): User's first name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        # Get environment variables
        from_email = os.environ.get('FROM_EMAIL', 'noreply@malavgajera.me')
        domain = os.environ.get('DOMAIN', 'demo.malavgajera.me')
        
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
                    <h2>Welcome to CSYE6225, {first_name}!</h2>
                    <p>Thank you for creating an account. Please verify your email address by clicking the link below:</p>
                    <p><a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block;">Verify Email Address</a></p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all;">{verification_link}</p>
                    <p><strong>This link will expire in 1 minute.</strong></p>
                    <p>If you did not create an account, please ignore this email.</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">This is an automated message from CSYE6225 Cloud Computing course.</p>
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
            
            # Extract data from message
            email = message_data.get('email')
            first_name = message_data.get('first_name', '')
            last_name = message_data.get('last_name', '')
            token = message_data.get('token')  # Token generated by webapp
            token_expiry = message_data.get('token_expiry')
            
            if not email:
                print("Error: No email provided in SNS message")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Email is required'})
                }
            
            if not token:
                print("Error: No token provided in SNS message")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Verification token is required'})
                }
            
            print(f"Processing verification for: {email}")
            print(f"User: {first_name} {last_name}")
            print(f"Token: {token}")
            print(f"Token Expiry: {token_expiry}")
            
            # ============================================================================
            # PHASE 9: Check if email already sent (prevent duplicates)
            # ============================================================================
            if check_email_already_sent(email, token):
                print(f"Duplicate email prevented for {email}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Email already sent for this token'})
                }
            
            # Send verification email
            if not send_verification_email(email, token, first_name):
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to send verification email'})
                }
            
            # Store record that email was sent
            store_email_sent_record(email, token)
            
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