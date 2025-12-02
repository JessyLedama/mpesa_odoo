# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    mpesa_transaction_ids = fields.One2many(
        'mpesa.transaction',
        'invoice_id',
        string='M-Pesa Transactions'
    )
    mpesa_transaction_count = fields.Integer(
        string='M-Pesa Transaction Count',
        compute='_compute_mpesa_transaction_count'
    )
    
    @api.depends('mpesa_transaction_ids')
    def _compute_mpesa_transaction_count(self):
        for record in self:
            record.mpesa_transaction_count = len(record.mpesa_transaction_ids)
    
    def action_send_mpesa_stk_push(self):
        """Open wizard to send STK Push for this invoice"""
        self.ensure_one()
        
        if self.move_type not in ['out_invoice']:
            return
        
        return {
            'name': 'Send M-Pesa Payment Request',
            'type': 'ir.actions.act_window',
            'res_model': 'mpesa.stk.push.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_amount': self.amount_residual,
                'default_phone_number': self.partner_id.phone or self.partner_id.mobile or '',
                'default_account_reference': self.name or '',
            }
        }
    
    def action_view_mpesa_transactions(self):
        """View M-Pesa transactions for this invoice"""
        self.ensure_one()
        
        return {
            'name': 'M-Pesa Transactions',
            'type': 'ir.actions.act_window',
            'res_model': 'mpesa.transaction',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id},
        }
