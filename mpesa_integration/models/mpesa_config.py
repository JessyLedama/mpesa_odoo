# -*- coding: utf-8 -*-

import base64
import logging
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MpesaConfig(models.Model):
    _name = 'mpesa.config'
    _description = 'M-Pesa Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='M-Pesa Configuration'
    )
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    # API Credentials
    consumer_key = fields.Char(
        string='Consumer Key',
        required=True,
        help='Consumer Key from Safaricom Daraja Portal'
    )
    consumer_secret = fields.Char(
        string='Consumer Secret',
        required=True,
        help='Consumer Secret from Safaricom Daraja Portal'
    )
    
    # Business Details
    shortcode = fields.Char(
        string='Business Shortcode',
        required=True,
        help='M-Pesa Paybill or Till Number'
    )
    passkey = fields.Char(
        string='Passkey',
        required=True,
        help='Passkey provided by Safaricom for STK Push'
    )
    business_type = fields.Selection([
        ('paybill', 'Paybill'),
        ('till', 'Buy Goods (Till Number)')
    ], string='Business Type', required=True, default='paybill')
    
    # Environment
    environment = fields.Selection([
        ('sandbox', 'Sandbox (Testing)'),
        ('production', 'Production (Live)')
    ], string='Environment', required=True, default='sandbox')
    
    # URLs (computed based on environment)
    base_url = fields.Char(
        string='Base URL',
        compute='_compute_urls',
        store=True
    )
    auth_url = fields.Char(
        string='Auth URL',
        compute='_compute_urls',
        store=True
    )
    stk_push_url = fields.Char(
        string='STK Push URL',
        compute='_compute_urls',
        store=True
    )
    stk_query_url = fields.Char(
        string='STK Query URL',
        compute='_compute_urls',
        store=True
    )
    c2b_register_url = fields.Char(
        string='C2B Register URL',
        compute='_compute_urls',
        store=True
    )
    
    # Callback URLs
    callback_url = fields.Char(
        string='Callback URL',
        help='URL for receiving STK Push payment results'
    )
    validation_url = fields.Char(
        string='Validation URL',
        help='URL for C2B payment validation'
    )
    confirmation_url = fields.Char(
        string='Confirmation URL',
        help='URL for C2B payment confirmation'
    )
    
    # Default Journal
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain=[('type', 'in', ['bank', 'cash'])],
        help='Default journal for M-Pesa payments'
    )
    
    # Token Management
    access_token = fields.Char(string='Access Token', readonly=True)
    token_expiry = fields.Datetime(string='Token Expiry', readonly=True)
    
    # C2B Registration Status
    c2b_registered = fields.Boolean(
        string='C2B URLs Registered',
        default=False,
        help='Whether C2B URLs have been registered with Safaricom'
    )
    
    @api.constrains('company_id', 'active')
    def _check_unique_active_config(self):
        """Ensure only one active configuration per company"""
        for record in self:
            if record.active:
                existing = self.search([
                    ('company_id', '=', record.company_id.id),
                    ('active', '=', True),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        'There can only be one active M-Pesa configuration per company!'
                    )
    
    @api.depends('environment')
    def _compute_urls(self):
        for record in self:
            if record.environment == 'production':
                record.base_url = 'https://api.safaricom.co.ke'
            else:
                record.base_url = 'https://sandbox.safaricom.co.ke'
            
            record.auth_url = f'{record.base_url}/oauth/v1/generate?grant_type=client_credentials'
            record.stk_push_url = f'{record.base_url}/mpesa/stkpush/v1/processrequest'
            record.stk_query_url = f'{record.base_url}/mpesa/stkpushquery/v1/query'
            record.c2b_register_url = f'{record.base_url}/mpesa/c2b/v1/registerurl'
    
    def get_access_token(self):
        """Get OAuth access token from Safaricom API"""
        self.ensure_one()
        
        # Check if current token is still valid
        if self.access_token and self.token_expiry:
            if fields.Datetime.now() < self.token_expiry:
                return self.access_token
        
        # Generate new token
        try:
            credentials = base64.b64encode(
                f'{self.consumer_key}:{self.consumer_secret}'.encode()
            ).decode()
            
            headers = {
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                self.auth_url,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            access_token = result.get('access_token')
            expires_in = int(result.get('expires_in', 3599))
            
            # Save token with expiry (subtract 60 seconds for safety margin)
            from datetime import timedelta
            self.write({
                'access_token': access_token,
                'token_expiry': fields.Datetime.now() + timedelta(seconds=expires_in - 60)
            })
            
            return access_token
            
        except requests.exceptions.RequestException as e:
            _logger.error(f'M-Pesa OAuth Error: {str(e)}')
            raise UserError(f'Failed to get M-Pesa access token: {str(e)}')
    
    def _generate_password(self, timestamp):
        """Generate password for STK Push"""
        import base64
        data = f'{self.shortcode}{self.passkey}{timestamp}'
        return base64.b64encode(data.encode()).decode()
    
    def initiate_stk_push(self, phone_number, amount, account_reference, description, invoice_id=None):
        """Initiate STK Push to customer's phone"""
        self.ensure_one()
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self._generate_password(timestamp)
        
        # Format phone number
        phone = self._format_phone_number(phone_number)
        
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Determine transaction type based on business type
        transaction_type = 'CustomerPayBillOnline' if self.business_type == 'paybill' else 'CustomerBuyGoodsOnline'
        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': transaction_type,
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': self.callback_url,
            'AccountReference': account_reference[:12] if account_reference else 'Payment',
            'TransactionDesc': description[:13] if description else 'Payment'
        }
        
        try:
            response = requests.post(
                self.stk_push_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # Log the transaction
            checkout_request_id = result.get('CheckoutRequestID')
            merchant_request_id = result.get('MerchantRequestID')
            
            transaction_vals = {
                'config_id': self.id,
                'transaction_type': 'stk_push',
                'checkout_request_id': checkout_request_id,
                'merchant_request_id': merchant_request_id,
                'phone_number': phone,
                'amount': amount,
                'account_reference': account_reference,
                'description': description,
                'state': 'pending',
                'invoice_id': invoice_id,
            }
            
            transaction = self.env['mpesa.transaction'].create(transaction_vals)
            
            return {
                'success': True,
                'checkout_request_id': checkout_request_id,
                'merchant_request_id': merchant_request_id,
                'transaction_id': transaction.id,
                'message': result.get('CustomerMessage', 'STK Push sent successfully')
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f'M-Pesa STK Push Error: {str(e)}')
            raise UserError(f'Failed to initiate M-Pesa payment: {str(e)}')
    
    def query_stk_push_status(self, checkout_request_id):
        """Query the status of an STK Push transaction"""
        self.ensure_one()
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self._generate_password(timestamp)
        
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id
        }
        
        try:
            response = requests.post(
                self.stk_query_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            _logger.error(f'M-Pesa Query Error: {str(e)}')
            raise UserError(f'Failed to query M-Pesa transaction: {str(e)}')
    
    def register_c2b_urls(self):
        """Register C2B URLs with Safaricom"""
        self.ensure_one()
        
        if not self.validation_url or not self.confirmation_url:
            raise UserError('Please set both Validation URL and Confirmation URL before registering.')
        
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'ShortCode': self.shortcode,
            'ResponseType': 'Completed',
            'ConfirmationURL': self.confirmation_url,
            'ValidationURL': self.validation_url
        }
        
        try:
            response = requests.post(
                self.c2b_register_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get('ResponseCode') == '0':
                self.c2b_registered = True
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'C2B URLs registered successfully!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(f'C2B Registration failed: {result.get("ResponseDescription", "Unknown error")}')
                
        except requests.exceptions.RequestException as e:
            _logger.error(f'M-Pesa C2B Registration Error: {str(e)}')
            raise UserError(f'Failed to register C2B URLs: {str(e)}')
    
    def _format_phone_number(self, phone):
        """Format phone number to 254XXXXXXXXX format"""
        phone = str(phone).strip()
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+254'):
            phone = phone[1:]
        elif phone.startswith('+'):
            # Remove leading + for other formats
            phone = phone[1:]
        elif not phone.startswith('254'):
            phone = '254' + phone
        
        # Validate Kenyan phone number format (254XXXXXXXXX - 12 digits)
        if not phone.startswith('254') or len(phone) != 12 or not phone.isdigit():
            raise ValidationError(
                'Invalid phone number format. Please enter a valid Kenyan phone number '
                '(e.g., 0712345678, +254712345678, or 254712345678).'
            )
        
        return phone
    
    def action_test_connection(self):
        """Test the M-Pesa API connection"""
        self.ensure_one()
        try:
            self.get_access_token()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': 'Successfully connected to M-Pesa API!',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def get_active_config(self, company_id=None):
        """Get the active M-Pesa configuration for a company"""
        if not company_id:
            company_id = self.env.company.id
        
        config = self.search([
            ('company_id', '=', company_id),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            raise UserError('No active M-Pesa configuration found. Please configure M-Pesa settings first.')
        
        return config
