# -*- coding: utf-8 -*-

import json
import logging

from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)


class MpesaController(http.Controller):
    """Controller for M-Pesa Daraja API callbacks"""

    @http.route('/mpesa/c2b/validation', type='json', auth='public', methods=['POST'], csrf=False)
    def c2b_validation(self, **kwargs):
        """
        C2B Validation callback URL
        This is called by M-Pesa before completing a C2B transaction
        Return {"ResultCode": 0} to accept or {"ResultCode": 1, "ResultDesc": "reason"} to reject
        """
        try:
            data = request.jsonrequest
            _logger.info(f'M-Pesa C2B Validation received: {data}')

            # Validate the transaction (you can add custom validation logic here)
            # For example, check if the account reference exists

            # Accept the transaction
            return {
                'ResultCode': 0,
                'ResultDesc': 'Accepted'
            }

        except Exception as e:
            _logger.error(f'M-Pesa C2B Validation error: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }

    @http.route('/mpesa/c2b/confirmation', type='json', auth='public', methods=['POST'], csrf=False)
    def c2b_confirmation(self, **kwargs):
        """
        C2B Confirmation callback URL
        This is called by M-Pesa after a successful C2B transaction
        """
        try:
            data = request.jsonrequest
            _logger.info(f'M-Pesa C2B Confirmation received: {data}')

            # Create transaction record
            with request.env.registry.cursor() as cr:
                env = request.env(cr, SUPERUSER_ID)
                env['mpesa.transaction'].create_from_callback(data, 'c2b')
                cr.commit()

            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }

        except Exception as e:
            _logger.error(f'M-Pesa C2B Confirmation error: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }

    @http.route('/mpesa/stkpush/callback', type='json', auth='public', methods=['POST'], csrf=False)
    def stk_push_callback(self, **kwargs):
        """
        STK Push callback URL
        This is called by M-Pesa after STK Push transaction completes
        """
        try:
            data = request.jsonrequest
            _logger.info(f'M-Pesa STK Push Callback received: {data}')

            # Update transaction record
            with request.env.registry.cursor() as cr:
                env = request.env(cr, SUPERUSER_ID)
                env['mpesa.transaction'].create_from_callback(data, 'stk_push')
                cr.commit()

            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }

        except Exception as e:
            _logger.error(f'M-Pesa STK Push Callback error: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }

    @http.route('/mpesa/result', type='json', auth='public', methods=['POST'], csrf=False)
    def result_callback(self, **kwargs):
        """
        General result callback URL
        Used for B2C, B2B, and other transaction types
        """
        try:
            data = request.jsonrequest
            _logger.info(f'M-Pesa Result Callback received: {data}')

            # Process based on transaction type
            # This can be extended for B2C, B2B, etc.

            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }

        except Exception as e:
            _logger.error(f'M-Pesa Result Callback error: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }

    @http.route('/mpesa/timeout', type='json', auth='public', methods=['POST'], csrf=False)
    def timeout_callback(self, **kwargs):
        """
        Timeout callback URL
        Called when a transaction times out
        """
        try:
            data = request.jsonrequest
            _logger.info(f'M-Pesa Timeout Callback received: {data}')

            # Handle timeout (update transaction status, notify user, etc.)

            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }

        except Exception as e:
            _logger.error(f'M-Pesa Timeout Callback error: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }

    @http.route('/mpesa/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health_check(self, **kwargs):
        """
        Health check endpoint for M-Pesa integration
        """
        return json.dumps({
            'status': 'ok',
            'message': 'M-Pesa integration is running'
        })
