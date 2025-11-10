"""
Unit Tests for Email Verification Lambda Function
Assignment 9 - CSYE6225
"""

import json
import pytest
import time
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
from botocore.exceptions import ClientError

# Import the Lambda function
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))
from lambda_function import (
    generate_verification_token,
    get_sendgrid_api_key,
    store_token_in_dynamodb,
    send_verification_email,
    lambda_handler
)


class TestGenerateVerificationToken:
    """Test token generation"""
    
    def test_token_generation_returns_string(self):
        """Test that token generation returns a string"""
        token = generate_verification_token("test@example.com")
        assert isinstance(token, str)
        assert len(token) == 64  # SHA256 hex = 64 characters
    
    def test_token_generation_unique(self):
        """Test that tokens are unique for same email"""
        email = "test@example.com"
        token1 = generate_verification_token(email)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        token2 = generate_verification_token(email)
        assert token1 != token2
    
    def test_token_generation_different_emails(self):
        """Test that different emails generate different tokens"""
        token1 = generate_verification_token("user1@example.com")
        token2 = generate_verification_token("user2@example.com")
        assert token1 != token2
    
    def test_token_generation_hex_format(self):
        """Test that token is valid hexadecimal"""
        token = generate_verification_token("test@example.com")
        try:
            int(token, 16)  # Should not raise ValueError
            assert True
        except ValueError:
            assert False, "Token is not valid hexadecimal"


class TestStoreDynamoDB:
    """Test DynamoDB storage operations"""
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_token_success(self, mock_get_dynamodb):
        """Test successful token storage"""
        # Mock DynamoDB
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        # Test
        email = "test@example.com"
        token = "test_token_123"
        result = store_token_in_dynamodb(email, token)
        
        # Assertions
        assert result is True
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        assert call_args[1]['Item']['email'] == email
        assert call_args[1]['Item']['token'] == token
        assert 'ttl' in call_args[1]['Item']
        assert 'created_at' in call_args[1]['Item']
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_token_with_custom_ttl(self, mock_get_dynamodb):
        """Test token storage with custom TTL"""
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        email = "test@example.com"
        token = "test_token_123"
        ttl_minutes = 5
        
        result = store_token_in_dynamodb(email, token, ttl_minutes)
        
        assert result is True
        call_args = mock_table.put_item.call_args
        stored_ttl = call_args[1]['Item']['ttl']
        expected_min_ttl = int(time.time()) + (ttl_minutes * 60) - 5  # 5 sec buffer
        assert stored_ttl >= expected_min_ttl
    
    @patch('lambda_function.get_dynamodb_client')
    def test_store_token_dynamodb_error(self, mock_get_dynamodb):
        """Test handling of DynamoDB errors"""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'PutItem'
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_get_dynamodb.return_value = mock_dynamodb
        
        result = store_token_in_dynamodb("test@example.com", "token")
        assert result is False


class TestSendEmail:
    """Test email sending functionality"""
    
    @patch('sendgrid.SendGridAPIClient')  # Patch at the sendgrid module level
    @patch('lambda_function.get_sendgrid_api_key')
    def test_send_email_success(self, mock_get_key, mock_sg_client):
        """Test successful email sending"""
        # Mock SendGrid
        mock_get_key.return_value = "test_api_key"
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sg_client.return_value = mock_sg_instance
        
        # Test
        email = "test@example.com"
        token = "test_token_123"
        result = send_verification_email(email, token)
        
        # Assertions
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
        
        result = send_verification_email("test@example.com", "token123")
        assert result is True
    
    @patch('sendgrid.SendGridAPIClient')
    @patch('lambda_function.get_sendgrid_api_key')
    def test_send_email_sendgrid_error(self, mock_get_key, mock_sg_client):
        """Test handling of SendGrid errors"""
        mock_get_key.return_value = "test_api_key"
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception("SendGrid API Error")
        mock_sg_client.return_value = mock_sg_instance
        
        result = send_verification_email("test@example.com", "token")
        assert result is False

class TestLambdaHandler:
    """Test main Lambda handler"""
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_token_in_dynamodb')
    @patch('lambda_function.generate_verification_token')
    def test_lambda_handler_success(self, mock_gen_token, mock_store, mock_send):
        """Test successful Lambda execution"""
        # Setup mocks
        mock_gen_token.return_value = "test_token_123"
        mock_store.return_value = True
        mock_send.return_value = True
        
        # Create test event
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'email': 'test@example.com',
                            'username': 'testuser'
                        })
                    }
                }
            ]
        }
        
        # Execute
        response = lambda_handler(event, None)
        
        # Assertions
        assert response['statusCode'] == 200
        assert 'successfully' in json.loads(response['body'])['message']
        mock_gen_token.assert_called_once_with('test@example.com')
        mock_store.assert_called_once()
        mock_send.assert_called_once()
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_token_in_dynamodb')
    @patch('lambda_function.generate_verification_token')
    def test_lambda_handler_no_email(self, mock_gen_token, mock_store, mock_send):
        """Test Lambda with missing email"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({
                            'username': 'testuser'
                        })
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_token_in_dynamodb')
    @patch('lambda_function.generate_verification_token')
    def test_lambda_handler_store_failure(self, mock_gen_token, mock_store, mock_send):
        """Test Lambda when DynamoDB storage fails"""
        mock_gen_token.return_value = "test_token"
        mock_store.return_value = False
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({'email': 'test@example.com'})
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 500
        assert 'store verification token' in json.loads(response['body'])['error']
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_token_in_dynamodb')
    @patch('lambda_function.generate_verification_token')
    def test_lambda_handler_email_failure(self, mock_gen_token, mock_store, mock_send):
        """Test Lambda when email sending fails"""
        mock_gen_token.return_value = "test_token"
        mock_store.return_value = True
        mock_send.return_value = False
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({'email': 'test@example.com'})
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 500
        assert 'send verification email' in json.loads(response['body'])['error']
    
    def test_lambda_handler_invalid_json(self):
        """Test Lambda with invalid JSON in SNS message"""
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': 'not valid json'
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
    
    @patch('lambda_function.send_verification_email')
    @patch('lambda_function.store_token_in_dynamodb')
    @patch('lambda_function.generate_verification_token')
    def test_lambda_handler_multiple_records(self, mock_gen_token, mock_store, mock_send):
        """Test Lambda with multiple SNS records"""
        mock_gen_token.return_value = "test_token"
        mock_store.return_value = True
        mock_send.return_value = True
        
        event = {
            'Records': [
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({'email': 'user1@example.com'})
                    }
                },
                {
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'Message': json.dumps({'email': 'user2@example.com'})
                    }
                }
            ]
        }
        
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert mock_gen_token.call_count == 2
        assert mock_store.call_count == 2
        assert mock_send.call_count == 2


class TestSecretsManager:
    """Test Secrets Manager integration"""
    
    @patch('lambda_function.get_secrets_client')
    def test_get_sendgrid_key_success(self, mock_get_client):
        """Test successful retrieval of SendGrid API key"""
        from lambda_function import get_sendgrid_api_key, sendgrid_api_key
        
        # Reset global variable
        import lambda_function
        lambda_function.sendgrid_api_key = None
        
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test_sendgrid_key'})
        }
        mock_get_client.return_value = mock_client
        
        key = get_sendgrid_api_key()
        assert key == 'test_sendgrid_key'
    
    @patch('lambda_function.get_secrets_client')
    def test_get_sendgrid_key_error(self, mock_get_client):
        """Test error handling when retrieving SendGrid key"""
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


# Run tests with: pytest tests/test_lambda_function.py -v --cov=src