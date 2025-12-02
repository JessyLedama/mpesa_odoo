# -*- coding: utf-8 -*-
{
    'name': 'M-Pesa Daraja Integration',
    'version': '19.0.1.0.0',
    'summary': 'M-Pesa Daraja API Integration for Odoo',
    'description': """
        M-Pesa Daraja API Integration Module
        =====================================
        This module integrates M-Pesa Daraja API with Odoo to:
        - Configure M-Pesa API credentials
        - Process C2B (Customer to Business) payments
        - Automatically detect payments and mark invoices/bills as paid
        - Track all M-Pesa transactions
        - Support STK Push for payment requests
    """,
    'category': 'Accounting/Payment',
    'author': 'Odoo Community',
    'website': 'https://github.com/JessyLedama/mpesa_odoo',
    'license': 'LGPL-3',
    'depends': ['account', 'base'],
    'data': [
        'security/mpesa_security.xml',
        'security/ir.model.access.csv',
        'wizard/mpesa_reconcile_wizard_views.xml',
        'views/mpesa_config_views.xml',
        'views/mpesa_transaction_views.xml',
        'views/mpesa_menu_views.xml',
        'views/account_move_views.xml',
        'data/mpesa_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        'python': ['requests'],
    },
}
