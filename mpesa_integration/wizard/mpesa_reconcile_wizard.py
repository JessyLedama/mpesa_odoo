# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MpesaReconcileWizard(models.TransientModel):
    _name = 'mpesa.reconcile.wizard'
    _description = 'M-Pesa Manual Reconciliation Wizard'

    transaction_id = fields.Many2one('mpesa.transaction', string='Transaction', required=True, readonly=True)
    amount = fields.Float(string='Transaction Amount', readonly=True)
    invoice_id = fields.Many2one('account.move', string='Invoice',
                                  domain=[('state', '=', 'posted'),
                                          ('payment_state', 'in', ['not_paid', 'partial']),
                                          ('move_type', 'in', ['out_invoice', 'in_invoice'])],
                                  required=True)
    invoice_amount = fields.Float(string='Invoice Amount', related='invoice_id.amount_residual', readonly=True)

    def action_reconcile(self):
        """Manually reconcile the transaction with selected invoice"""
        self.ensure_one()

        if self.transaction_id.is_reconciled:
            raise UserError(_('This transaction is already reconciled.'))

        if self.transaction_id.state != 'completed':
            raise UserError(_('Only completed transactions can be reconciled.'))

        # Perform reconciliation
        result = self.transaction_id._reconcile_with_invoice(self.invoice_id)

        if result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Transaction reconciled successfully with invoice %s') % self.invoice_id.name,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        else:
            raise UserError(_('Failed to reconcile transaction. Please check the payment journal configuration.'))
