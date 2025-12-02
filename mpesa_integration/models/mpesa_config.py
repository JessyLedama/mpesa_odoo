# -*- coding: utf-8 -*-

import base64
import logging
import requests
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# M-Pesa API Constants (as per Daraja API documentation)
MPESA_ACCOUNT_REFERENCE_MAX_LENGTH = 12  # Max chars for AccountReference field
MPESA_TRANSACTION_DESC_MAX_LENGTH = 13   # Max chars for TransactionDesc field


class MpesaConfig(models.Model):
    _name = 'mpesa.config'
    _description = 'M-Pesa Daraja API Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True, default='M-Pesa Configuration')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)

    # Environment settings
    environment = fields.Selection([
        ('sandbox', 'Sandbox (Testing)'),
        ('production', 'Production (Live)')
    ], string='Environment', required=True, default='sandbox')

    # API Credentials
    consumer_key = fields.Char(string='Consumer Key', required=True)
    consumer_secret = fields.Char(string='Consumer Secret', required=True)

    # Business Details
    shortcode = fields.Char(string='Business Shortcode', required=True,
                            help='Your M-Pesa Paybill or Till Number')
    business_name = fields.Char(string='Business Name')
    passkey = fields.Char(string='Passkey', required=True,
                          help='Lipa Na M-Pesa Online Passkey')

    # Initiator credentials (for B2C, B2B, etc.)
    initiator_name = fields.Char(string='Initiator Name')
    security_credential = fields.Char(string='Security Credential')

    # URLs
    callback_url = fields.Char(string='Callback URL',
                               help='URL where M-Pesa will send transaction results')
    validation_url = fields.Char(string='Validation URL',
                                 help='URL for C2B validation')
    confirmation_url = fields.Char(string='Confirmation URL',
                                   help='URL for C2B confirmation')
    timeout_url = fields.Char(string='Timeout URL',
                              help='URL for timeout notifications')
    result_url = fields.Char(string='Result URL',
                             help='URL for transaction results')

    # Token management
    access_token = fields.Char(string='Access Token', readonly=True)
    token_expiry = fields.Datetime(string='Token Expiry', readonly=True)

    # Default account for payments
    default_journal_id = fields.Many2one('account.journal', string='Default Payment Journal',
                                          domain=[('type', 'in', ['bank', 'cash'])])

    # Statistics
    transaction_count = fields.Integer(string='Transaction Count', compute='_compute_transaction_count')

    @api.depends('shortcode')
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = self.env['mpesa.transaction'].search_count([
                ('config_id', '=', record.id)
            ])

    def _get_base_url(self):
        """Get base URL based on environment"""
        self.ensure_one()
        if self.environment == 'sandbox':
            return 'https://sandbox.safaricom.co.ke'
        return 'https://api.safaricom.co.ke'

    def _get_access_token(self):
        """Get OAuth access token from M-Pesa API"""
        self.ensure_one()
        now = fields.Datetime.now()

        # Return cached token if still valid
        if self.access_token and self.token_expiry and self.token_expiry > now:
            return self.access_token

        base_url = self._get_base_url()
        url = '%s/oauth/v1/generate?grant_type=client_credentials' % base_url

        # Create Basic Auth credentials
        credentials = base64.b64encode(
            ('%s:%s' % (self.consumer_key, self.consumer_secret)).encode()
        ).decode()

        headers = {
            'Authorization': 'Basic %s' % credentials,
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            access_token = result.get('access_token')
            expires_in = int(result.get('expires_in', 3599))

            # Store token with expiry (subtract 60 seconds for safety)
            self.write({
                'access_token': access_token,
                'token_expiry': now + timedelta(seconds=expires_in - 60)
            })

            return access_token

        except requests.exceptions.RequestException as e:
            _logger.error('Failed to get M-Pesa access token: %s', str(e))
            raise UserError(_('Failed to authenticate with M-Pesa: %s') % str(e))

    def _generate_password(self, timestamp):
        """Generate Lipa Na M-Pesa password"""
        self.ensure_one()
        data_to_encode = '%s%s%s' % (self.shortcode, self.passkey, timestamp)
        return base64.b64encode(data_to_encode.encode()).decode('utf-8')

    def action_test_connection(self):
        """Test the M-Pesa API connection"""
        self.ensure_one()
        try:
            token = self._get_access_token()
            if token:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to M-Pesa API!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_register_urls(self):
        """Register C2B URLs with M-Pesa"""
        self.ensure_one()
        if not self.validation_url or not self.confirmation_url:
            raise UserError(_('Please configure Validation URL and Confirmation URL first.'))

        access_token = self._get_access_token()
        base_url = self._get_base_url()
        url = '%s/mpesa/c2b/v1/registerurl' % base_url

        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': 'application/json',
        }

        payload = {
            'ShortCode': self.shortcode,
            'ResponseType': 'Completed',
            'ConfirmationURL': self.confirmation_url,
            'ValidationURL': self.validation_url,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()

            if result.get('ResponseCode') == '0':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('URLs Registered'),
                        'message': _('C2B URLs registered successfully!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Failed to register URLs: %s') % result.get('ResponseDescription', 'Unknown error'))

        except requests.exceptions.RequestException as e:
            _logger.error('Failed to register C2B URLs: %s', str(e))
            raise UserError(_('Failed to register URLs: %s') % str(e))

    def initiate_stk_push(self, phone_number, amount, account_reference, description, invoice_id=None):
        """Initiate STK Push (Lipa Na M-Pesa Online)"""
        self.ensure_one()

        access_token = self._get_access_token()
        base_url = self._get_base_url()
        url = '%s/mpesa/stkpush/v1/processrequest' % base_url

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self._generate_password(timestamp)

        # Format phone number
        phone = self._format_phone_number(phone_number)

        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': 'application/json',
        }

        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': self.callback_url,
            'AccountReference': account_reference[:MPESA_ACCOUNT_REFERENCE_MAX_LENGTH] if account_reference else 'Payment',
            'TransactionDesc': description[:MPESA_TRANSACTION_DESC_MAX_LENGTH] if description else 'Payment',
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()

            # Create transaction record
            transaction_vals = {
                'config_id': self.id,
                'transaction_type': 'stk_push',
                'phone_number': phone,
                'amount': amount,
                'account_reference': account_reference,
                'description': description,
                'merchant_request_id': result.get('MerchantRequestID'),
                'checkout_request_id': result.get('CheckoutRequestID'),
                'state': 'pending' if result.get('ResponseCode') == '0' else 'failed',
                'response_code': result.get('ResponseCode'),
                'response_description': result.get('ResponseDescription'),
            }

            if invoice_id:
                transaction_vals['invoice_id'] = invoice_id

            transaction = self.env['mpesa.transaction'].create(transaction_vals)

            return {
                'success': result.get('ResponseCode') == '0',
                'transaction_id': transaction.id,
                'merchant_request_id': result.get('MerchantRequestID'),
                'checkout_request_id': result.get('CheckoutRequestID'),
                'response_description': result.get('ResponseDescription'),
            }

        except requests.exceptions.RequestException as e:
            _logger.error('Failed to initiate STK Push: %s', str(e))
            raise UserError(_('Failed to initiate payment: %s') % str(e))

    def query_stk_status(self, checkout_request_id):
        """Query the status of an STK Push transaction"""
        self.ensure_one()

        access_token = self._get_access_token()
        base_url = self._get_base_url()
        url = '%s/mpesa/stkpushquery/v1/query' % base_url

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self._generate_password(timestamp)

        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': 'application/json',
        }

        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to query STK status: %s', str(e))
            raise UserError(_('Failed to query payment status: %s') % str(e))

    @staticmethod
    def _format_phone_number(phone):
        """Format phone number to M-Pesa format (254XXXXXXXXX)"""
        phone = str(phone).strip().replace(' ', '').replace('-', '').replace('+', '')

        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone
        elif not phone.startswith('254'):
            phone = '254' + phone

        return phone

    def action_view_transactions(self):
        """View all transactions for this configuration"""
        self.ensure_one()
        return {
            'name': _('M-Pesa Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'mpesa.transaction',
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id},
        }

    @api.model
    def get_active_config(self, company_id=None):
        """Get the active M-Pesa configuration for a company"""
        if not company_id:
            company_id = self.env.company.id

        config = self.search([
            ('active', '=', True),
            ('company_id', '=', company_id)
        ], limit=1)

        if not config:
            raise UserError(_('No active M-Pesa configuration found. Please configure M-Pesa settings first.'))

        return config
