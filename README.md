# M-Pesa Daraja Integration for Odoo 19

A comprehensive Odoo 19 module for integrating M-Pesa Daraja API for seamless payment processing.

## Features

- **M-Pesa API Configuration**: Easy setup of Daraja API credentials
- **STK Push Payments**: Send payment requests directly to customer phones
- **C2B Payments**: Receive and process C2B payments automatically
- **Automatic Invoice Reconciliation**: Payments are automatically matched and reconciled with invoices
- **Transaction Tracking**: Complete transaction history with status tracking
- **Multi-company Support**: Configure different M-Pesa accounts per company

## Installation

1. Copy the `mpesa_integration` folder to your Odoo addons directory
2. Update the apps list in Odoo
3. Install the "M-Pesa Daraja Integration" module

## Configuration

1. Navigate to **Accounting → M-Pesa → Configuration**
2. Create a new configuration with your Daraja API credentials:
   - Consumer Key
   - Consumer Secret
   - Business Shortcode
   - Passkey
3. Set up callback URLs (must be publicly accessible HTTPS endpoints):
   - STK Callback: `https://yourdomain.com/mpesa/callback/stk`
   - C2B Validation: `https://yourdomain.com/mpesa/callback/c2b/validation`
   - C2B Confirmation: `https://yourdomain.com/mpesa/callback/c2b/confirmation`
4. Select a payment journal for M-Pesa transactions
5. Test the connection using the "Test Connection" button

## Usage

### Sending Payment Requests (STK Push)

1. Open a posted customer invoice
2. Click the "Request M-Pesa Payment" button
3. Enter the customer's phone number and verify the amount
4. Click "Send Payment Request"
5. The customer will receive an STK push on their phone

### Viewing Transactions

Navigate to **Accounting → M-Pesa → Transactions** to view all M-Pesa transactions.

### Automatic Payment Processing

When a payment is completed:
1. The transaction status is updated automatically via callbacks
2. If linked to an invoice, a payment is created automatically
3. The payment is reconciled with the invoice

## Menu Structure

Under **Accounting**:
- **M-Pesa**
  - Transactions
    - Completed
    - Pending
  - Configuration (Manager only)

## Security

The module includes two security groups:
- **M-Pesa Manager**: Full access to configurations and all transactions
- **M-Pesa User**: Can initiate transactions and view their own transactions

## API Endpoints

The module exposes the following callback endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/mpesa/callback/stk` | STK Push callback |
| `/mpesa/callback/c2b/validation` | C2B payment validation |
| `/mpesa/callback/c2b/confirmation` | C2B payment confirmation |

## Requirements

- Odoo 19
- `account` module (Accounting)
- Valid Safaricom Daraja API credentials

## Getting Daraja API Credentials

1. Register at [Safaricom Developer Portal](https://developer.safaricom.co.ke/)
2. Create a new app
3. Get your Consumer Key and Consumer Secret
4. For production, apply for a live shortcode

## License

LGPL-3

## Author

Odoo Community
