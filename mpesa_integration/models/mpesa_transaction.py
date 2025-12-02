# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MpesaTransaction(models.Model):
    _name = 'mpesa.transaction'
    _description = 'M-Pesa Transaction'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True
    )
    
    config_id = fields.Many2one(
        'mpesa.config',
        string='M-Pesa Configuration',
        required=True,
        ondelete='restrict'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True
    )
    
    # Transaction Type
    transaction_type = fields.Selection([
        ('stk_push', 'STK Push'),
        ('c2b', 'C2B Payment'),
        ('b2c', 'B2C Payment'),
    ], string='Transaction Type', required=True, default='stk_push')
    
    # M-Pesa Reference IDs
    checkout_request_id = fields.Char(string='Checkout Request ID', index=True)
    merchant_request_id = fields.Char(string='Merchant Request ID')
    mpesa_receipt_number = fields.Char(string='M-Pesa Receipt Number', index=True)
    transaction_id = fields.Char(string='Transaction ID', index=True)
    
    # Transaction Details
    phone_number = fields.Char(string='Phone Number', required=True)
    amount = fields.Float(string='Amount', required=True, digits=(12, 2))
    account_reference = fields.Char(string='Account Reference')
    description = fields.Char(string='Description')
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True, index=True)
    
    result_code = fields.Char(string='Result Code')
    result_description = fields.Text(string='Result Description')
    
    # Callback Data
    callback_data = fields.Text(string='Callback Raw Data')
    transaction_date = fields.Datetime(string='Transaction Date')
    
    # Related Invoice
    invoice_id = fields.Many2one(
        'account.move',
        string='Related Invoice',
        domain=[('move_type', 'in', ['out_invoice', 'in_invoice'])],
        ondelete='set null'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='invoice_id.partner_id',
        store=True
    )
    
    # Payment Record
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        readonly=True
    )
    
    @api.depends('mpesa_receipt_number', 'checkout_request_id', 'transaction_type')
    def _compute_display_name(self):
        for record in self:
            if record.mpesa_receipt_number:
                record.display_name = record.mpesa_receipt_number
            elif record.checkout_request_id:
                record.display_name = record.checkout_request_id[:20]
            else:
                type_label = record.transaction_type.upper() if record.transaction_type else 'MPESA'
                record_id = record.id if record.id else 'New'
                record.display_name = f'{type_label} - {record_id}'
    
    def process_stk_callback(self, callback_data):
        """Process STK Push callback from Safaricom"""
        import json
        
        _logger.info(f'Processing STK callback: {callback_data}')
        
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = str(stk_callback.get('ResultCode'))
        result_desc = stk_callback.get('ResultDesc')
        
        # Find the transaction
        transaction = self.search([
            ('checkout_request_id', '=', checkout_request_id)
        ], limit=1)
        
        if not transaction:
            _logger.warning(f'Transaction not found for checkout_request_id: {checkout_request_id}')
            return False
        
        # Update transaction with callback data
        vals = {
            'callback_data': json.dumps(callback_data),
            'result_code': result_code,
            'result_description': result_desc,
        }
        
        if result_code == '0':
            # Payment successful
            vals['state'] = 'completed'
            
            # Extract metadata
            metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            for item in metadata:
                name = item.get('Name')
                value = item.get('Value')
                if name == 'MpesaReceiptNumber':
                    vals['mpesa_receipt_number'] = value
                elif name == 'TransactionDate':
                    # Parse transaction date (format: YYYYMMDDHHmmss)
                    from datetime import datetime
                    try:
                        dt = datetime.strptime(str(value), '%Y%m%d%H%M%S')
                        vals['transaction_date'] = dt
                    except Exception:
                        pass
                elif name == 'Amount':
                    vals['amount'] = float(value)
        else:
            # Payment failed or cancelled
            if result_code == '1032':
                vals['state'] = 'cancelled'  # User cancelled
            else:
                vals['state'] = 'failed'
        
        transaction.write(vals)
        
        # If payment successful and linked to invoice, create payment
        if vals.get('state') == 'completed' and transaction.invoice_id:
            transaction._create_payment_for_invoice()
        
        return True
    
    def process_c2b_confirmation(self, data):
        """Process C2B payment confirmation from Safaricom"""
        import json
        from datetime import datetime
        
        _logger.info(f'Processing C2B confirmation: {data}')
        
        # Extract data from C2B callback
        trans_id = data.get('TransID')
        trans_amount = float(data.get('TransAmount', 0))
        bill_ref_number = data.get('BillRefNumber', '')
        msisdn = data.get('MSISDN')
        trans_time = data.get('TransTime')
        
        # Find config by shortcode
        shortcode = data.get('BusinessShortCode')
        config = self.env['mpesa.config'].search([
            ('shortcode', '=', shortcode),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            _logger.warning(f'No active config found for shortcode: {shortcode}')
            return False
        
        # Parse transaction time (M-Pesa format: YYYYMMDDHHmmss)
        trans_date = None
        if trans_time:
            trans_time_str = str(trans_time)
            for fmt in ['%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S', '%Y%m%d']:
                try:
                    trans_date = datetime.strptime(trans_time_str, fmt)
                    break
                except ValueError:
                    continue
            if trans_date is None:
                trans_date = datetime.now()
                _logger.warning(f'Could not parse M-Pesa transaction time: {trans_time}')
        
        # Create transaction record
        vals = {
            'config_id': config.id,
            'transaction_type': 'c2b',
            'mpesa_receipt_number': trans_id,
            'transaction_id': trans_id,
            'phone_number': msisdn,
            'amount': trans_amount,
            'account_reference': bill_ref_number,
            'state': 'completed',
            'transaction_date': trans_date,
            'callback_data': json.dumps(data),
        }
        
        # Try to find related invoice by reference
        if bill_ref_number:
            invoice = self._find_invoice_by_reference(bill_ref_number)
            if invoice:
                vals['invoice_id'] = invoice.id
        
        transaction = self.create(vals)
        
        # Create payment if invoice found
        if transaction.invoice_id:
            transaction._create_payment_for_invoice()
        
        return True
    
    def _find_invoice_by_reference(self, reference):
        """Find invoice by various reference fields"""
        # Search by invoice name/number
        invoice = self.env['account.move'].search([
            ('name', 'ilike', reference),
            ('move_type', 'in', ['out_invoice']),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid'),
        ], limit=1)
        
        if not invoice:
            # Search by partner reference
            invoice = self.env['account.move'].search([
                ('ref', 'ilike', reference),
                ('move_type', 'in', ['out_invoice']),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ], limit=1)
        
        return invoice
    
    def _create_payment_for_invoice(self):
        """Create payment and reconcile with invoice"""
        self.ensure_one()
        
        if not self.invoice_id or self.payment_id:
            return False
        
        if self.invoice_id.payment_state == 'paid':
            return False
        
        # Get payment journal from config
        journal = self.config_id.journal_id
        if not journal:
            _logger.warning('No payment journal configured for M-Pesa')
            return False
        
        # Determine payment type
        payment_type = 'inbound' if self.invoice_id.move_type == 'out_invoice' else 'outbound'
        
        # Create payment
        payment_vals = {
            'partner_id': self.invoice_id.partner_id.id,
            'amount': self.amount,
            'payment_type': payment_type,
            'journal_id': journal.id,
            'ref': f'M-Pesa: {self.mpesa_receipt_number or self.checkout_request_id}',
            'date': self.transaction_date.date() if self.transaction_date else fields.Date.today(),
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        self.payment_id = payment.id
        
        # Reconcile payment with invoice
        try:
            # Get receivable/payable lines
            invoice_lines = self.invoice_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
            )
            payment_lines = payment.line_ids.filtered(
                lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
            )
            
            if invoice_lines and payment_lines:
                (invoice_lines + payment_lines).reconcile()
        except Exception as e:
            _logger.error(f'Error reconciling payment: {str(e)}')
        
        return True
    
    def action_query_status(self):
        """Query the status of pending STK Push transaction"""
        self.ensure_one()
        
        if self.transaction_type != 'stk_push' or not self.checkout_request_id:
            return
        
        result = self.config_id.query_stk_push_status(self.checkout_request_id)
        
        result_code = str(result.get('ResultCode'))
        result_desc = result.get('ResultDesc')
        
        vals = {
            'result_code': result_code,
            'result_description': result_desc,
        }
        
        if result_code == '0':
            vals['state'] = 'completed'
        elif result_code == '1032':
            vals['state'] = 'cancelled'
        elif result_code and result_code != '':
            vals['state'] = 'failed'
        
        self.write(vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Status Updated',
                'message': result_desc,
                'type': 'info' if result_code == '0' else 'warning',
                'sticky': False,
            }
        }
    
    def action_view_invoice(self):
        """Open related invoice"""
        self.ensure_one()
        if not self.invoice_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_payment(self):
        """Open related payment"""
        self.ensure_one()
        if not self.payment_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
