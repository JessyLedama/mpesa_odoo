# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MpesaController(http.Controller):
    """Controller for handling M-Pesa API callbacks"""
    
    @http.route(
        '/mpesa/callback/stk',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def stk_callback(self, **kwargs):
        """Handle STK Push callback from Safaricom"""
        _logger.info('Received STK Push callback')
        
        try:
            # Get the raw data from the request
            data = request.jsonrequest
            _logger.info(f'STK Callback data: {json.dumps(data)}')
            
            # Process the callback
            transaction_model = request.env['mpesa.transaction'].sudo()
            transaction_model.process_stk_callback(data)
            
            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }
            
        except Exception as e:
            _logger.error(f'Error processing STK callback: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }
    
    @http.route(
        '/mpesa/callback/c2b/validation',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def c2b_validation(self, **kwargs):
        """Handle C2B validation callback from Safaricom"""
        _logger.info('Received C2B validation callback')
        
        try:
            data = request.jsonrequest
            _logger.info(f'C2B Validation data: {json.dumps(data)}')
            
            # Accept all transactions by default
            # You can add custom validation logic here
            return {
                'ResultCode': 0,
                'ResultDesc': 'Accepted'
            }
            
        except Exception as e:
            _logger.error(f'Error processing C2B validation: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }
    
    @http.route(
        '/mpesa/callback/c2b/confirmation',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def c2b_confirmation(self, **kwargs):
        """Handle C2B confirmation callback from Safaricom"""
        _logger.info('Received C2B confirmation callback')
        
        try:
            data = request.jsonrequest
            _logger.info(f'C2B Confirmation data: {json.dumps(data)}')
            
            # Process the confirmation
            transaction_model = request.env['mpesa.transaction'].sudo()
            transaction_model.process_c2b_confirmation(data)
            
            return {
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }
            
        except Exception as e:
            _logger.error(f'Error processing C2B confirmation: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }
    
    @http.route(
        '/mpesa/callback/timeout',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def timeout_callback(self, **kwargs):
        """Handle timeout callback from Safaricom"""
        _logger.info('Received timeout callback')
        
        try:
            data = request.jsonrequest
            _logger.info(f'Timeout data: {json.dumps(data)}')
            
            return {
                'ResultCode': 0,
                'ResultDesc': 'Received'
            }
            
        except Exception as e:
            _logger.error(f'Error processing timeout callback: {str(e)}')
            return {
                'ResultCode': 1,
                'ResultDesc': str(e)
            }
