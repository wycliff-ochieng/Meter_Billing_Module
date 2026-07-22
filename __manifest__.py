{
    'name': 'Account Meter Billing',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add meter reading columns (Previous, New, Actual) to invoice lines and auto-map to quantity.',
    'description': """
        Extends the Accounting module to support utility/meter-based billing.
        - Adds Previous, New, and Actual meter reading columns to invoice line items.
        - 'Previous' is auto-populated from the last posted invoice for the same partner + product.
        - 'Actual' is computed as New - Previous and mapped to the standard Quantity field.
        - Columns render in both the invoice form view and the printed PDF report.
    """,
    'author': 'Wycliff Ochieng',
    'depends': ['account_accountant'],
    'data': [
        'views/account_move_views.xml',
        'views/product_views.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
