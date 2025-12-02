# M-Pesa Daraja API Integration for Odoo

This module integrates Safaricom's M-Pesa Daraja API with Odoo, enabling seamless payment processing and automatic invoice reconciliation.

## Features

- **M-Pesa Configuration**: Store and manage your M-Pesa API credentials securely
- **STK Push**: Send payment requests directly to customer phones
- **C2B Payments**: Receive Customer-to-Business payments automatically
- **Automatic Reconciliation**: Payments are automatically matched and reconciled with invoices
- **Transaction Tracking**: Full history of all M-Pesa transactions
- **Multi-company Support**: Configure different M-Pesa accounts for different companies

## Installation

1. Copy the `mpesa_integration` folder to your Odoo addons directory
2. Update the app list in Odoo
3. Install the "M-Pesa Daraja Integration" module

## Configuration

1. Navigate to **Accounting > M-Pesa > Configuration**
2. Create a new configuration with your M-Pesa credentials:
   - Consumer Key (from Safaricom Daraja portal)
   - Consumer Secret (from Safaricom Daraja portal)
   - Business Shortcode (Paybill or Till number)
   - Passkey (for Lipa Na M-Pesa Online)
3. Configure callback URLs:
   - STK Push Callback: `https://yourdomain.com/mpesa/stkpush/callback`
   - C2B Validation: `https://yourdomain.com/mpesa/c2b/validation`
   - C2B Confirmation: `https://yourdomain.com/mpesa/c2b/confirmation`
4. Set a default payment journal (Bank or Cash)
5. Click "Test Connection" to verify your credentials
6. Click "Register URLs" to register C2B callbacks with M-Pesa

## Usage

### Requesting Payment (STK Push)

1. Open a posted invoice
2. Click the "Request M-Pesa Payment" button
3. Customer receives a payment prompt on their phone
4. Upon successful payment, the invoice is automatically marked as paid

### C2B Payments

1. Customers pay to your Paybill/Till number
2. M-Pesa sends confirmation to your callback URL
3. Transaction is recorded and matched with the invoice
4. Invoice is automatically marked as paid

### Manual Reconciliation

If a payment is not automatically matched:
1. Go to **Accounting > M-Pesa > Transactions**
2. Find the unreconciled transaction
3. Click "Manual Reconciliation"
4. Select the invoice to reconcile with

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/mpesa/c2b/validation` | C2B payment validation |
| `/mpesa/c2b/confirmation` | C2B payment confirmation |
| `/mpesa/stkpush/callback` | STK Push result callback |
| `/mpesa/result` | General result callback |
| `/mpesa/timeout` | Timeout callback |
| `/mpesa/health` | Health check endpoint |

## Requirements

- Odoo 19.0 or higher
- Python `requests` library
- Active Safaricom Daraja API credentials
- Publicly accessible callback URLs (for production)

## Obtaining Daraja API Credentials

1. Visit [Safaricom Daraja Portal](https://developer.safaricom.co.ke/)
2. Create an account and log in
3. Create a new app to get your Consumer Key and Secret
4. For production, request API access from Safaricom

## Security

- API credentials are stored securely in the database
- Access is controlled via Odoo's security groups
- Callback endpoints validate requests appropriately

## Support

For issues and feature requests, please create an issue on the GitHub repository.

## License

LGPL-3
