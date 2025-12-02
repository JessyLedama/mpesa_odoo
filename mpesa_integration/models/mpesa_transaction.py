# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MpesaTransaction(models.Model):
    _name = 'mpesa.transaction'
    _description = 'M-Pesa Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'transaction_id'

    # Configuration
    config_id = fields.Many2one('mpesa.config', string='M-Pesa Config', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', string='Company', related='config_id.company_id', store=True)

    # Transaction identifiers
    transaction_id = fields.Char(string='M-Pesa Transaction ID', index=True,
                                  help='The unique M-Pesa receipt number')
    merchant_request_id = fields.Char(string='Merchant Request ID')
    checkout_request_id = fields.Char(string='Checkout Request ID', index=True)
    conversation_id = fields.Char(string='Conversation ID')
    originator_conversation_id = fields.Char(string='Originator Conversation ID')

    # Transaction details
    transaction_type = fields.Selection([
        ('c2b', 'C2B (Customer to Business)'),
        ('b2c', 'B2C (Business to Customer)'),
        ('stk_push', 'STK Push'),
        ('reversal', 'Reversal'),
    ], string='Transaction Type', required=True)

    phone_number = fields.Char(string='Phone Number')
    amount = fields.Float(string='Amount', digits=(12, 2))
    account_reference = fields.Char(string='Account Reference',
                                     help='Bill/Invoice number used for matching')
    description = fields.Char(string='Description')
    transaction_time = fields.Datetime(string='Transaction Time')

    # Payment details
    bill_ref_number = fields.Char(string='Bill Reference Number')
    msisdn = fields.Char(string='MSISDN')
    first_name = fields.Char(string='First Name')
    middle_name = fields.Char(string='Middle Name')
    last_name = fields.Char(string='Last Name')

    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reconciled', 'Reconciled'),
    ], string='Status', default='pending', required=True, tracking=True)

    # Response details
    response_code = fields.Char(string='Response Code')
    response_description = fields.Char(string='Response Description')
    result_code = fields.Char(string='Result Code')
    result_description = fields.Char(string='Result Description')

    # Linked invoice/payment
    invoice_id = fields.Many2one('account.move', string='Invoice',
                                  domain=[('move_type', 'in', ['out_invoice', 'in_invoice'])])
    payment_id = fields.Many2one('account.payment', string='Payment')
    is_reconciled = fields.Boolean(string='Is Reconciled', default=False)

    # Raw data for debugging
    raw_request = fields.Text(string='Raw Request')
    raw_response = fields.Text(string='Raw Response')
    callback_data = fields.Text(string='Callback Data')

    # Note: PostgreSQL allows multiple NULLs in unique constraints by default,
    # so pending transactions (with transaction_id = NULL) won't violate uniqueness
    _sql_constraints = [
        ('transaction_id_unique', 'unique(transaction_id)',
         'M-Pesa Transaction ID must be unique!'),
    ]

    @api.depends('transaction_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.transaction_id or 'TXN-%s' % record.id

    @api.model
    def create_from_callback(self, callback_data, transaction_type='c2b'):
        """Create transaction record from M-Pesa callback data"""
        _logger.info('Creating transaction from callback: %s', callback_data)

        if transaction_type == 'c2b':
            return self._create_c2b_transaction(callback_data)
        elif transaction_type == 'stk_push':
            return self._update_stk_transaction(callback_data)

        return False

    def _create_c2b_transaction(self, data):
        """Create C2B transaction from callback data"""
        config = self.env['mpesa.config'].search([
            ('shortcode', '=', data.get('BusinessShortCode')),
            ('active', '=', True)
        ], limit=1)

        if not config:
            _logger.error("No config found for shortcode: %s", data.get('BusinessShortCode'))
            return False

        # Parse transaction time
        trans_time = data.get('TransTime', '')
        transaction_time = False
        if trans_time:
            try:
                transaction_time = fields.Datetime.to_datetime(
                    '%s-%s-%s %s:%s:%s' % (
                        trans_time[:4], trans_time[4:6], trans_time[6:8],
                        trans_time[8:10], trans_time[10:12], trans_time[12:14]
                    )
                )
            except (ValueError, IndexError):
                _logger.warning('Could not parse transaction time: %s', trans_time)

        transaction = self.create({
            'config_id': config.id,
            'transaction_id': data.get('TransID'),
            'transaction_type': 'c2b',
            'phone_number': data.get('MSISDN'),
            'msisdn': data.get('MSISDN'),
            'amount': float(data.get('TransAmount', 0)),
            'account_reference': data.get('BillRefNumber'),
            'bill_ref_number': data.get('BillRefNumber'),
            'first_name': data.get('FirstName'),
            'middle_name': data.get('MiddleName'),
            'last_name': data.get('LastName'),
            'transaction_time': transaction_time,
            'state': 'completed',
            'callback_data': str(data),
        })

        # Try to match and reconcile with invoice
        transaction._auto_reconcile()

        return transaction

    def _update_stk_transaction(self, data):
        """Update STK Push transaction from callback data"""
        body = data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = body.get('CheckoutRequestID')

        transaction = self.search([
            ('checkout_request_id', '=', checkout_request_id)
        ], limit=1)

        if not transaction:
            _logger.error('No transaction found for CheckoutRequestID: %s', checkout_request_id)
            return False

        result_code = str(body.get('ResultCode', ''))
        result_desc = body.get('ResultDesc', '')

        vals = {
            'result_code': result_code,
            'result_description': result_desc,
            'callback_data': str(data),
        }

        if result_code == '0':
            # Successful transaction
            vals['state'] = 'completed'

            # Extract callback metadata
            metadata = body.get('CallbackMetadata', {}).get('Item', [])
            for item in metadata:
                name = item.get('Name')
                value = item.get('Value')
                if name == 'MpesaReceiptNumber':
                    vals['transaction_id'] = value
                elif name == 'TransactionDate':
                    try:
                        trans_time = str(value)
                        vals['transaction_time'] = fields.Datetime.to_datetime(
                            '%s-%s-%s %s:%s:%s' % (
                                trans_time[:4], trans_time[4:6], trans_time[6:8],
                                trans_time[8:10], trans_time[10:12], trans_time[12:14]
                            )
                        )
                    except (ValueError, IndexError):
                        pass
                elif name == 'PhoneNumber':
                    vals['phone_number'] = str(value)
                elif name == 'Amount':
                    vals['amount'] = float(value)
        else:
            # Failed or cancelled
            if result_code == '1032':
                vals['state'] = 'cancelled'
            else:
                vals['state'] = 'failed'

        transaction.write(vals)

        # Try to reconcile if successful
        if vals.get('state') == 'completed':
            transaction._auto_reconcile()

        return transaction

    def _auto_reconcile(self):
        """Automatically match and reconcile with invoice"""
        self.ensure_one()

        if self.is_reconciled or self.state != 'completed':
            return False

        # Try to find matching invoice by account reference
        invoice = self._find_matching_invoice()

        if invoice:
            return self._reconcile_with_invoice(invoice)

        return False

    def _find_matching_invoice(self):
        """Find invoice matching this transaction"""
        self.ensure_one()
        Invoice = self.env['account.move']

        # If invoice is already linked
        if self.invoice_id:
            return self.invoice_id

        # Search by account reference (bill reference)
        if self.account_reference or self.bill_ref_number:
            ref = self.account_reference or self.bill_ref_number

            # Try exact match on invoice name/number
            invoice = Invoice.search([
                ('name', '=', ref),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if invoice:
                return invoice

            # Try match on reference field
            invoice = Invoice.search([
                ('ref', '=', ref),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if invoice:
                return invoice

            # Try partial match
            invoice = Invoice.search([
                '|',
                ('name', 'ilike', ref),
                ('ref', 'ilike', ref),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if invoice:
                return invoice

        return False

    def _reconcile_with_invoice(self, invoice):
        """Create payment and reconcile with invoice"""
        self.ensure_one()

        if self.is_reconciled:
            return False

        config = self.config_id
        journal = config.default_journal_id

        if not journal:
            _logger.warning('No default payment journal configured for M-Pesa')
            return False

        try:
            # Determine payment type based on invoice type
            if invoice.move_type == 'out_invoice':
                payment_type = 'inbound'
                partner_type = 'customer'
            else:
                payment_type = 'outbound'
                partner_type = 'supplier'

            # Create payment
            payment_vals = {
                'payment_type': payment_type,
                'partner_type': partner_type,
                'partner_id': invoice.partner_id.id,
                'amount': self.amount,
                'currency_id': invoice.currency_id.id,
                'journal_id': journal.id,
                'date': self.transaction_time.date() if self.transaction_time else fields.Date.today(),
                'ref': 'M-Pesa: %s' % self.transaction_id,
                'mpesa_transaction_id': self.id,
            }

            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()

            # Update transaction
            self.write({
                'invoice_id': invoice.id,
                'payment_id': payment.id,
                'is_reconciled': True,
                'state': 'reconciled',
            })

            # Reconcile payment with invoice
            if invoice.payment_state in ['not_paid', 'partial']:
                # Get receivable/payable lines
                invoice_lines = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                )
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                )

                if invoice_lines and payment_lines:
                    (invoice_lines + payment_lines).reconcile()

            _logger.info('Successfully reconciled M-Pesa transaction %s with invoice %s', self.transaction_id, invoice.name)
            return True

        except Exception as e:
            _logger.error('Failed to reconcile transaction %s: %s', self.transaction_id, str(e))
            return False

    def action_reconcile_manually(self):
        """Open wizard to manually reconcile transaction"""
        self.ensure_one()
        return {
            'name': _('Reconcile M-Pesa Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'mpesa.reconcile.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transaction_id': self.id,
                'default_amount': self.amount,
            },
        }

    def action_view_invoice(self):
        """View linked invoice"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No invoice linked to this transaction.'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_payment(self):
        """View linked payment"""
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('No payment linked to this transaction.'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_retry_reconcile(self):
        """Retry automatic reconciliation"""
        self.ensure_one()
        if self._auto_reconcile():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reconciliation Successful'),
                    'message': _('Transaction has been reconciled with invoice.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reconciliation Failed'),
                    'message': _('Could not find matching invoice. Please reconcile manually.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def _cron_check_pending_transactions(self):
        """
        Cron job to check status of pending STK Push transactions
        and retry reconciliation for completed but unreconciled transactions
        """
        _logger.info('Running M-Pesa pending transactions check')

        # Check pending STK Push transactions
        pending_stk = self.search([
            ('state', '=', 'pending'),
            ('transaction_type', '=', 'stk_push'),
            ('checkout_request_id', '!=', False),
        ], limit=100)

        for transaction in pending_stk:
            try:
                config = transaction.config_id
                result = config.query_stk_status(transaction.checkout_request_id)
                result_code = str(result.get('ResultCode', ''))

                # M-Pesa STK Push Result Codes:
                # 0 - Success
                # 1032 - Request cancelled by user
                # 1037 - DS timeout (transaction timed out)
                # 2001 - Wrong PIN entered
                # 17 - Rule limited (transaction amount limit exceeded)
                if result_code == '0':
                    transaction.write({
                        'state': 'completed',
                        'result_code': result_code,
                        'result_description': result.get('ResultDesc'),
                    })
                    transaction._auto_reconcile()
                elif result_code in ['1032', '1037']:
                    # 1032: User cancelled, 1037: DS timeout
                    transaction.write({
                        'state': 'cancelled',
                        'result_code': result_code,
                        'result_description': result.get('ResultDesc'),
                    })
                elif result_code:
                    # Any other non-empty code is a failure
                    transaction.write({
                        'state': 'failed',
                        'result_code': result_code,
                        'result_description': result.get('ResultDesc'),
                    })
            except Exception as e:
                _logger.warning('Error checking STK status for %s: %s', transaction.id, str(e))

        # Retry reconciliation for completed but unreconciled transactions
        unreconciled = self.search([
            ('state', '=', 'completed'),
            ('is_reconciled', '=', False),
        ], limit=100)

        for transaction in unreconciled:
            try:
                transaction._auto_reconcile()
            except Exception as e:
                _logger.warning('Error reconciling transaction %s: %s', transaction.id, str(e))
