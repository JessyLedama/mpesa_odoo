# -*- coding: utf-8 -*-
{
    'name': 'M-Pesa Daraja Integration',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'M-Pesa Daraja API Integration for Odoo',
    'description': """
        M-Pesa Daraja API Integration for Odoo 19
        ==========================================
        
        This module integrates M-Pesa Daraja API with Odoo for seamless payment processing.
        
        Features:
        ---------
        * M-Pesa API configuration
        * STK Push for payment collection
        * C2B payment registration and handling
        * Automatic payment detection and invoice reconciliation
        * Transaction logging and tracking
        
        Configuration:
        --------------
        1. Go to Accounting > M-Pesa > Configuration
        2. Enter your Daraja API credentials
        3. Configure callback URLs
        4. Register C2B URLs if needed
    """,
    'author': 'Odoo Community',
    'website': 'https://github.com/JessyLedama/mpesa_odoo',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
    ],
    'data': [
        'security/mpesa_security.xml',
        'security/ir.model.access.csv',
        'data/mpesa_data.xml',
        'views/mpesa_config_views.xml',
        'views/mpesa_transaction_views.xml',
        'views/account_move_views.xml',
        'views/mpesa_menu_views.xml',
        'wizard/mpesa_stk_push_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
