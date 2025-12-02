# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class MpesaStkPushWizard(models.TransientModel):
    _name = 'mpesa.stk.push.wizard'
    _description = 'M-Pesa STK Push Wizard'

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        domain=[('move_type', '=', 'out_invoice')],
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='invoice_id.partner_id',
        readonly=True
    )
    
    phone_number = fields.Char(
        string='Phone Number',
        required=True,
        help='Customer phone number in format 254XXXXXXXXX or 07XXXXXXXX'
    )
    amount = fields.Float(
        string='Amount',
        required=True,
        digits=(12, 2)
    )
    account_reference = fields.Char(
        string='Account Reference',
        required=True,
        help='Reference to appear on customer\'s phone (max 12 chars)'
    )
    description = fields.Char(
        string='Description',
        default='Payment',
        help='Transaction description (max 13 chars)'
    )
    
    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.amount = self.invoice_id.amount_residual
            self.account_reference = self.invoice_id.name or ''
            # Try to get phone from partner
            partner = self.invoice_id.partner_id
            if partner:
                self.phone_number = partner.phone or partner.mobile or ''
    
    def action_send_stk_push(self):
        """Send STK Push to customer"""
        self.ensure_one()
        
        if not self.phone_number:
            raise UserError('Please enter a phone number.')
        
        if not self.amount or self.amount <= 0:
            raise UserError('Please enter a valid amount.')
        
        # Get M-Pesa configuration
        config = self.env['mpesa.config'].get_active_config()
        
        # Initiate STK Push
        result = config.initiate_stk_push(
            phone_number=self.phone_number,
            amount=self.amount,
            account_reference=self.account_reference or 'Payment',
            description=self.description or 'Payment',
            invoice_id=self.invoice_id.id if self.invoice_id else None
        )
        
        if result.get('success'):
            message = result.get('message', 'STK Push sent successfully!')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }
        else:
            raise UserError('Failed to send STK Push. Please try again.')
