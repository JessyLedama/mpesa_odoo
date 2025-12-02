# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    mpesa_transaction_ids = fields.One2many('mpesa.transaction', 'invoice_id', string='M-Pesa Transactions')
    mpesa_transaction_count = fields.Integer(string='M-Pesa Transactions', compute='_compute_mpesa_transaction_count')

    @api.depends('mpesa_transaction_ids')
    def _compute_mpesa_transaction_count(self):
        for record in self:
            record.mpesa_transaction_count = len(record.mpesa_transaction_ids)

    def action_mpesa_stk_push(self):
        """Initiate M-Pesa STK Push payment request"""
        self.ensure_one()

        if self.state != 'posted':
            raise UserError(_('Invoice must be posted before requesting payment.'))

        if self.payment_state == 'paid':
            raise UserError(_('Invoice is already paid.'))

        if self.move_type not in ['out_invoice', 'in_invoice']:
            raise UserError(_('M-Pesa payment can only be requested for invoices.'))

        # Get partner phone number
        partner = self.partner_id
        phone = partner.mobile or partner.phone

        if not phone:
            raise UserError(_('Partner does not have a phone number configured.'))

        # Get M-Pesa configuration
        config = self.env['mpesa.config'].get_active_config(self.company_id.id)

        # Initiate STK Push
        result = config.initiate_stk_push(
            phone_number=phone,
            amount=self.amount_residual,
            account_reference=self.name,
            description=f'Payment for {self.name}',
            invoice_id=self.id
        )

        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Payment Request Sent'),
                    'message': _('M-Pesa payment request has been sent to %s') % phone,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Payment Request Failed'),
                    'message': result.get('response_description', _('Unknown error')),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_mpesa_transactions(self):
        """View M-Pesa transactions linked to this invoice"""
        self.ensure_one()
        return {
            'name': _('M-Pesa Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'mpesa.transaction',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id},
        }


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    mpesa_transaction_id = fields.Many2one('mpesa.transaction', string='M-Pesa Transaction', readonly=True)
