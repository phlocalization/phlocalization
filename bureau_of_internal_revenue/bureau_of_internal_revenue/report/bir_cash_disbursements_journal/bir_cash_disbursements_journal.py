# Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    """Entry point for the BIR Cash Disbursements Journal report."""
    filters = frappe._dict(filters or {})
    if not filters.get("company"):
        frappe.throw("Company filter is required.")
    if not filters.get("from_date"):
        frappe.throw("From Date filter is required.")
    if not filters.get("to_date"):
        frappe.throw("To Date filter is required.")
    if filters.from_date > filters.to_date:
        frappe.throw("From Date must be less than or equal to To Date.")

    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    """Return column definitions for the Cash Disbursements Journal."""
    return [
        {"fieldname": "transaction_date", "label": "Transaction Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "vendor_name", "label": "Vendor Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "vendor_address", "label": "Vendor Address", "fieldtype": "Data", "width": 200},
        {"fieldname": "vendor_tin", "label": "Vendor TIN", "fieldtype": "Data", "width": 120},
        {"fieldname": "check_no", "label": "Check No", "fieldtype": "Data", "width": 160},
        {"fieldname": "doc_no", "label": "Doc No", "fieldtype": "Link", "options": "Payment Entry", "width": 160},
        {"fieldname": "po_exp_no", "label": "PO/EXP No", "fieldtype": "Data", "width": 130},
        {"fieldname": "ap_no", "label": "AP No", "fieldtype": "Data", "width": 130},
        {"fieldname": "pv_no", "label": "PV No", "fieldtype": "Data", "width": 130},
        {"fieldname": "account_name_dr", "label": "Account Name (DR)", "fieldtype": "Data", "width": 200},
        {"fieldname": "accounts_payable_dr", "label": "Accounts Payable (DR)", "fieldtype": "Currency", "width": 140},
        {"fieldname": "cash_amount", "label": "Cash Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "check_amount", "label": "Check Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "credit_card_amount", "label": "Credit Card Amount", "fieldtype": "Currency", "width": 130},
        {"fieldname": "wtax", "label": "WTAX", "fieldtype": "Currency", "width": 100},
        {"fieldname": "notes", "label": "Notes", "fieldtype": "Data", "width": 200},
    ]


def get_data(filters):
    """Fetch cash disbursement rows from Payment Entry and its references."""
    query = """
    SELECT
        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN pe.posting_date         ELSE NULL END                         AS transaction_date,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN pe.party_name           ELSE '' END                           AS vendor_name,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN IFNULL((
            SELECT a.address_line1
            FROM `tabAddress` a
            INNER JOIN `tabDynamic Link` dl ON dl.parent = a.name
            WHERE dl.link_doctype = 'Supplier' AND dl.link_name = pe.party
            LIMIT 1
        ), '') ELSE '' END                                                   AS vendor_address,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN IFNULL((
            SELECT s.tax_id FROM `tabSupplier` s
            WHERE s.name = pe.party LIMIT 1
        ), '') ELSE '' END                                                   AS vendor_tin,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN pe.reference_no         ELSE '' END                           AS check_no,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN pe.name                 ELSE '' END                           AS doc_no,

        NULL                                                                 AS po_exp_no,

        IFNULL(per.reference_name, '')                                       AS ap_no,
        IFNULL(per.reference_name, '')                                       AS pv_no,

        pe.paid_from                                                         AS account_name_dr,

        IFNULL(per.allocated_amount, 0)                                      AS accounts_payable_dr,

        pe.paid_amount                                                       AS cash_amount,

        pe.paid_amount                                                       AS check_amount,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN 0                       ELSE NULL END                         AS credit_card_amount,

        IFNULL((
            CASE
                WHEN per.reference_doctype = 'Purchase Invoice' THEN (
                    SELECT SUM(ptc.tax_amount)
                    FROM `tabPurchase Taxes and Charges` ptc
                    WHERE ptc.parent = per.reference_name
                      AND ptc.account_head LIKE '2505%%'
                )
                WHEN per.reference_doctype = 'Journal Entry' THEN (
                    SELECT SUM(jea.credit_in_account_currency)
                    FROM `tabJournal Entry Account` jea
                    WHERE jea.parent = per.reference_name
                      AND (jea.account LIKE '2504%%' OR jea.account LIKE '2505%%')
                      AND jea.credit_in_account_currency > 0
                )
            END
        ), 0)                                                                AS wtax,

        CASE WHEN per.name IS NULL OR per.idx = (
            SELECT MIN(p2.idx) FROM `tabPayment Entry Reference` p2
            WHERE p2.parent = pe.name AND p2.reference_doctype IN ('Purchase Invoice', 'Journal Entry')
        ) THEN pe.remarks              ELSE '' END                           AS notes

    FROM `tabPayment Entry` pe

    LEFT JOIN `tabPayment Entry Reference` per
        ON per.parent = pe.name
        AND per.reference_doctype IN ('Purchase Invoice', 'Journal Entry')

    WHERE
        pe.docstatus = 1
        AND pe.company = %(company)s
        AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND pe.payment_type = 'Pay'
        AND pe.party_type = 'Supplier'

    ORDER BY
        pe.posting_date ASC,
        pe.name ASC,
        per.idx ASC
    """
    return frappe.db.sql(query, filters, as_dict=True)