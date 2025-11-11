"""
Unit Tests for Email Verification Lambda Function
Assignment 9 - CSYE6225
Tests for Lambda that receives token from webapp and sends emails
"""

import json
import pytest
import time
from datetime import datetime
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Import the Lambda function
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))
from lambda_function import (
    get_sendgrid_api_key,
    check_email_already_sent,
    store_email_sent_record,
    send_verification_email,
    lambda_handler
)


class TestCheckEmailAlreadySent:
    """Test duplicate email checking"""
    
    @patch('lambda_function.get_dynamodb_client')
    def test_email_not_sent_yet(self, mock_get_dynamodb):
        """Test when email has not been sent yet"""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # No item found
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = check_email_already_sent("test@example.com", "token123")
        assert result is False
    
    @patch('lambda_function.get_dynamodb_client')
    def test_email_already_sent_same_token(self, mock_get_dynamodb):
        """Test when email was already sent with same token"""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'email': 'test@example.com',
                'token': 'token123',
                'email_sent': True
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = check_email_already_sent("test@example.com", "token123")
        assert result is True
    
    @patch('lambda_function.get_dynamodb_client')
    def test_email_different_token(self, mock_get_dynamodb):
        """Test when email exists but with different token"""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'email': 'test@example.com',
                'token': 'old_token',
                'email_sent': True
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = check_email_already_sent("test@example.com", "new_token")
        assert result is False
    
    @patch('lambda_function.get_dynamodb_client')
    def test_email_dynamodb_error(self, mock_get_dynamodb):
        """Test handling of DynamoDB errors (fail open)"""
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'GetItem'
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Should return False (fail open) to allow email to be sent
        result = check_email_already_sent("test@example.com", "token123")
        assert result is False


class TestStoreEmailSentRecord:
    """Test storing email sent records"""
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_record_success(self, mock_get_dynamodb):
        """Test successful record storage"""
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = store_email_sent_record("test@example.com", "token123")
        
        assert result is True
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        assert call_args[1]['Item']['email'] == "test@example.com"
        assert call_args[1]['Item']['token'] == "token123"
        assert call_args[1]['Item']['email_sent'] is True
        assert 'ttl' in call_args[1]['Item']
        assert 'sent_at' in call_args[1]['Item']
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_record_with_custom_ttl(self, mock_get_dynamodb):
        """Test storing record with custom TTL"""
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        ttl_minutes = 5
        result = store_email_sent_record("test@example.com", "token123", ttl_minutes)
        
        assert result is True
        call_args = mock_table.put_item.call_args
        stored_ttl = call_args[1]['Item']['ttl']
        expected_min_ttl = int(time.time()) + (ttl_minutes * 60) - 5
        assert stored_ttl >= expected_min_ttl
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_record_error(self, mock_get_dynamodb):
        """Test error handling when storing record"""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'PutItem'
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = store_email_sent_record("test@example.com", "token123")
        assert result is False


class TestSendVerificationEmail:
    """Test email sending functionality"""
    
    @patch('sendgrid.SendGridAPIClient')
    @patch('lambda_function.get_sendgrid_api_key')
    def test_send_email_success(self, mock_get_key, mock_sg_client):
        """Test successful email sending"""
        mock_get_key.return_value = "test_api_key"
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sg_client.return_value = mock_sg_instance
        
        result = send_verification_email("test@example.com", "token123", "John")
        
        assert result is True
        mock_sg_instance.send.assert_called_once()
    
    @patch('sendgrid.SendGridAPIClient')
    @patch('lambda_function.get_sendgrid_api_key')
    def test_send_email_with_custom_domain(self, mock_get_key, mock_sg_client):
        """Test email with custom domain"""
        mock_get_key.return_value = "test_api_key"
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sg_client.return_value = mock_sg_instance
        
        os.environ['DOMAIN'] = 'custom.example.com'
        os.environ['FROM_EMAIL'] = 'noreply@custom.example.com'
        
        result = send_verification_email("test@example.com", "token123", "Jane")
        assert result is True
    
    @patch('sendgrid.SendGridAPIClient')
    @patch('lambda_function.get_sendgrid_api_key')
    def test_send_email_error(self, mock_get_key, mock_sg_client):
        """Test error handling when sending email"""
        mock_get_key.return_value = "test_api_key"
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception("SendGrid API Error")
        mock_sg_client.return_value = mock_sg_instance
        
        result = send_verification_email("test@example.com", "token123", "John")
        assert result is False


class TestLambdaHandler:
    """Test main Lambda handler"""
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_success(self, mock_check, mock_store, mock_send):
        """Test successful Lambda execution"""
        mock_check.return_value = False  # Email not sent yet
        mock_store.return_value = True
        mock_send.return_value = True
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'test@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'token': 'abc123xyz',
                            'token_expiry': '2025-01-15T10:05:00Z'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        assert 'successfully' in json.loads(response['body'])['message']
        mock_check.assert_called_once_with('test@example.com', 'abc123xyz')
        mock_send.assert_called_once_with('test@example.com', 'abc123xyz', 'John')
        mock_store.assert_called_once_with('test@example.com', 'abc123xyz')
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_duplicate_prevention(self, mock_check, mock_store, mock_send):
        """Test that duplicate emails are prevented"""
        mock_check.return_value = True  # Email already sent
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'test@example.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'token': 'abc123xyz',
                            'token_expiry': '2025-01-15T10:05:00Z'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        assert 'already sent' in json.loads(response['body'])['message']
        mock_check.assert_called_once()
        # Email should NOT be sent again
        mock_send.assert_not_called()
        mock_store.assert_not_called()
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_missing_email(self, mock_check, mock_store, mock_send):
        """Test Lambda with missing email"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'first_name': 'John',
                            'token': 'abc123xyz'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Email is required' in json.loads(response['body'])['error']
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_missing_token(self, mock_check, mock_store, mock_send):
        """Test Lambda with missing token"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'test@example.com',
                            'first_name': 'John'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'token is required' in json.loads(response['body'])['error']
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_email_send_failure(self, mock_check, mock_store, mock_send):
        """Test Lambda when email sending fails"""
        mock_check.return_value = False
        mock_send.return_value = False  # Email sending failed
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'test@example.com',
                            'first_name': 'John',
                            'token': 'abc123xyz',
                            'token_expiry': '2025-01-15T10:05:00Z'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 500
        assert 'Failed to send' in json.loads(response['body'])['error']
    
    def test_lambda_handler_invalid_json(self):
        """Test Lambda with invalid JSON"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': 'not valid json {]'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Invalid JSON' in json.loads(response['body'])['error']
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_email_sent_record')
    @patch('lambda_function.check_email_already_sent')
    def test_lambda_handler_multiple_records(self, mock_check, mock_store, mock_send):
        """Test Lambda with multiple SNS records"""
        mock_check.return_value = False
        mock_store.return_value = True
        mock_send.return_value = True
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'user1@example.com',
                            'first_name': 'User1',
                            'token': 'token1'
                        })
                    }
                },
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'user2@example.com',
                            'first_name': 'User2',
                            'token': 'token2'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert mock_check.call_count == 2
        assert mock_send.call_count == 2
        assert mock_store.call_count == 2
    
    def test_lambda_handler_non_sns_event(self):
        """Test Lambda skips non-SNS events"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:s3',
                    'S3': {'bucket': {'name': 'test-bucket'}}
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200


class TestSecretsManager:
    """Test Secrets Manager integration"""
    
    @patch('lambda_function.get_secrets_client')
    def test_get_sendgrid_key_success(self, mock_get_client):
        """Test successful retrieval of SendGrid API key"""
        # Reset global variable
        import lambda_function
        lambda_function.sendgrid_api_key = None
        
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'SG.test_key_12345'})
        }
        mock_get_client.return_value = mock_client
        
        key = get_sendgrid_api_key()
        assert key == 'SG.test_key_12345'
    
    @patch('lambda_function.get_secrets_client')
    def test_get_sendgrid_key_cached(self, mock_get_client):
        """Test that API key is cached after first retrieval"""
        import lambda_function
        lambda_function.sendgrid_api_key = 'cached_key'
        
        key = get_sendgrid_api_key()
        assert key == 'cached_key'
        # Should not call AWS if already cached
        mock_get_client.assert_not_called()
    
    @patch('lambda_function.get_secrets_client')
    def test_get_sendgrid_key_error(self, mock_get_client):
        """Test error handling when retrieving key"""
        import lambda_function
        lambda_function.sendgrid_api_key = None
        
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
            'GetSecretValue'
        )
        mock_get_client.return_value = mock_client
        
        with pytest.raises(ClientError):
            get_sendgrid_api_key()


# Run tests with: pytest tests/test_lambda_function.py -v