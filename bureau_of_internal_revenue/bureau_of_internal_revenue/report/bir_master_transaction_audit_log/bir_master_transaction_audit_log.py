# Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""
  Entry point Frappe calls to render the report.
	Returns a (columns, data) tuple based on the supplied filters.
	Short-circuits to empty output when filters or data are missing.
	"""
	if not filters:
		return [], []
	columns = get_columns()
	data = get_data(filters)
	if not data:
		return columns, []
	return columns, data


def get_columns():
	"""
  Define the ordered list of column definitions for the report.
	Each entry maps a field to its label, type, and display width.
	The final four columns expose audit metadata (owner and timestamps).
	"""
	return [
		{"label": "Account",               "fieldname": "account",           "fieldtype": "Link",         "options": "Account",      "width": 250},
		{"label": "Cost Center",            "fieldname": "cost_center",       "fieldtype": "Link",         "options": "Cost Center",  "width": 160},
		{"label": "Doc Type",               "fieldname": "doc_type",          "fieldtype": "Data",                                    "width": 160},
		{"label": "Doc No",                 "fieldname": "doc_no",            "fieldtype": "Dynamic Link", "options": "doc_type",     "width": 150},
		{"label": "Pay Type",               "fieldname": "doc_type_label",    "fieldtype": "Data",                                    "width": 80},
		{"label": "Reference",              "fieldname": "reference_no",      "fieldtype": "Data",                                    "width": 140},
		{"label": "Tran Date",              "fieldname": "transaction_date",  "fieldtype": "Date",                                    "width": 100},
		{"label": "Payee/Received From",    "fieldname": "party",             "fieldtype": "Data",                                    "width": 220},
		{"label": "Particulars",            "fieldname": "particulars",       "fieldtype": "Data",                                    "width": 400},
		{"label": "Beginning Balance",      "fieldname": "beginning_balance", "fieldtype": "Currency",                                "width": 130},
		{"label": "Debit (Transaction)",    "fieldname": "debit",             "fieldtype": "Currency",                                "width": 130},
		{"label": "Credit (Transaction)",   "fieldname": "credit",            "fieldtype": "Currency",                                "width": 130},
		{"label": "Debit (Net Change)",     "fieldname": "net_debit",         "fieldtype": "Currency",                                "width": 130},
		{"label": "Credit (Net Change)",    "fieldname": "net_credit",        "fieldtype": "Currency",                                "width": 130},
		{"label": "Debit (Balance)",        "fieldname": "balance_debit",     "fieldtype": "Currency",                                "width": 130},
		{"label": "Credit (Balance)",       "fieldname": "balance_credit",    "fieldtype": "Currency",                                "width": 130},
		{"label": "Status",                 "fieldname": "status",            "fieldtype": "Data",                                    "width": 100},
		{"label": "Owner",                  "fieldname": "owner",             "fieldtype": "Link",         "options": "User",         "width": 160},
		{"label": "Creation Date",          "fieldname": "creation",          "fieldtype": "Datetime",                                "width": 160},
		{"label": "Modified By",            "fieldname": "modified_by",       "fieldtype": "Link",         "options": "User",         "width": 160},
		{"label": "Modified Time",          "fieldname": "modified",          "fieldtype": "Datetime",                                "width": 160},
	]


def get_data(filters):
	"""
  Build and run the SQL that assembles every report row.
	Combines beginning balances, transaction details, subtotals, and totals.
	Returns the query result as a list of dicts for the report engine.

	Status column logic (ported from BIR Stock Audit Trail):
	  Posted    -> GL Entry with is_cancelled = 0
	  Cancelled -> GL Entry with is_cancelled = 1
	The Status filter (All / Posted / Cancelled Transactions, default Posted)
	is applied to in-period transaction queries only. Pre-period beginning-balance
	subqueries stay posted-only so opening balances remain correct.
	"""
	sql = """
WITH
accounts_with_txn AS (
  SELECT DISTINCT g.account
  FROM `tabGL Entry` g
  WHERE g.docstatus = 1
    AND (
      COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
      OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(g.is_cancelled, 0) = 0)
      OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(g.is_cancelled, 0) = 1)
    )
    AND g.company = %(company)s
    AND g.posting_date BETWEEN %(from_date)s AND %(to_date)s
),
accounts_with_bb AS (
  SELECT gle.account
  FROM `tabGL Entry` gle
  WHERE gle.docstatus = 1
    AND IFNULL(gle.is_cancelled, 0) = 0
    AND gle.company = %(company)s
    AND gle.posting_date < %(from_date)s
  GROUP BY gle.account
  HAVING ROUND(SUM(gle.debit - gle.credit), 2) <> 0
),
accounts_in_scope_raw AS (
  SELECT account FROM accounts_with_txn
  UNION
  SELECT account FROM accounts_with_bb
),
accounts_in_scope AS (
  SELECT air.account
  FROM accounts_in_scope_raw air
  JOIN `tabAccount` a
    ON a.name = air.account AND a.company = %(company)s
  WHERE
    %(account)s = 'All Accounts'
    OR (
      %(account)s = 'Cost of Sales Accounts'
      AND a.account_type = 'Cost of Goods Sold'
    )
)

SELECT
    account,
    cost_center,
    doc_type,
    doc_no,
    doc_type_label,
    reference_no,
    transaction_date,
    party,
    particulars,
    beginning_balance,
    debit,
    credit,
    net_debit,
    net_credit,
    balance_debit,
    balance_credit,
    status,
    owner,
    creation,
    modified_by,
    modified
FROM (

    /* ======== BEGINNING BALANCE ROW ======== */
    SELECT
        gle.account AS account,
        NULL AS cost_center,
        NULL AS transaction_date,
        NULL AS doc_type,
        NULL AS doc_type_label,
        NULL AS doc_no,
        NULL AS reference_no,
        NULL AS party,
        '<b>BEGINNING BALANCE </b>' AS particulars,
        SUM(gle.debit - gle.credit) AS beginning_balance,
        NULL AS debit,
        NULL AS credit,
        NULL AS net_debit,
        NULL AS net_credit,
        NULL AS balance_debit,
        NULL AS balance_credit,
        NULL AS status,
        NULL AS owner,
        NULL AS creation,
        NULL AS modified_by,
        NULL AS modified,
        CONCAT(gle.account, '-1') AS sort_order,
        NULL AS dept_code
    FROM `tabGL Entry` gle
    WHERE gle.docstatus = 1
      AND IFNULL(gle.is_cancelled, 0) = 0
      AND gle.company = %(company)s
      AND gle.posting_date < %(from_date)s
      AND gle.account IN (SELECT account FROM accounts_in_scope)
    GROUP BY gle.account

    UNION ALL

    /* ======== TRANSACTION DETAIL ROWS ======== */
    SELECT
        g.account AS account,
        g.cost_center AS cost_center,
        g.posting_date AS transaction_date,
        g.voucher_type AS doc_type,
        CASE
          WHEN g.voucher_type = 'Payment Entry' THEN
            CASE
              WHEN COALESCE(g.voucher_subtype, pe.payment_type) = 'Pay'               THEN 'Pay'
              WHEN COALESCE(g.voucher_subtype, pe.payment_type) = 'Receive'           THEN 'Receive'
              WHEN COALESCE(g.voucher_subtype, pe.payment_type) = 'Internal Transfer' THEN 'Int. Transfer'
              ELSE COALESCE(g.voucher_subtype, pe.payment_type, '')
            END
          ELSE NULL
        END AS doc_type_label,
        g.voucher_no AS doc_no,
        COALESCE(
          pe.reference_no,
          je.cheque_no,
          si.remarks,
          pi.remarks,
          sr.name,
          g.against_voucher
        ) AS reference_no,
        /* ---- PAYEE / RECEIVED FROM ---- */
        CASE
          WHEN g.voucher_type = 'Journal Entry'
            THEN COALESCE(cust_je.customer_name, supp_je.supplier_name, emp_je.employee_name, g.party, jea.party)
          WHEN g.voucher_type = 'Payment Entry'
            THEN COALESCE(NULLIF(TRIM(pe.party_name), ''), pe.party, g.party)
          WHEN g.voucher_type = 'Sales Invoice'
            THEN si.customer_name
          WHEN g.voucher_type = 'Purchase Invoice'
            THEN pi.supplier
          WHEN g.voucher_type = 'Purchase Receipt'
            THEN COALESCE(pr.supplier, pr.supplier_name)
          ELSE g.party
        END AS party,
        /* ---- PARTICULARS ---- */
        CASE
            /* Pay: PI items -> JE user_remark -> PE remarks -> PE Ref names -> party */
            WHEN g.voucher_type = 'Payment Entry'
              AND COALESCE(g.voucher_subtype, pe.payment_type) = 'Pay'
                THEN COALESCE(
                       NULLIF(TRIM(pi_items.description), ''),
                       NULLIF(TRIM(je_items.user_remark), ''),
                       NULLIF(TRIM(pe.remarks), ''),
                       NULLIF(TRIM(per.ref_names), ''),
                       NULLIF(TRIM(pe.party_name), ''),
                       g.against
                     )

            /* Receive: SI items -> PE remarks -> PE Ref names -> party */
            WHEN g.voucher_type = 'Payment Entry'
              AND COALESCE(g.voucher_subtype, pe.payment_type) = 'Receive'
                THEN COALESCE(
                       NULLIF(TRIM(si_items.description), ''),
                       NULLIF(TRIM(pe.remarks), ''),
                       NULLIF(TRIM(per.ref_names), ''),
                       NULLIF(TRIM(pe.party_name), ''),
                       g.against
                     )

            WHEN acc.account_type IN ('Payable', 'Receivable')
                THEN g.party

            WHEN g.voucher_type = 'Journal Entry'
                THEN COALESCE(
                       NULLIF(TRIM(jea.user_remark), ''),
                       NULLIF(TRIM(SUBSTRING_INDEX(COALESCE(g.remarks,''), 'Note:', 1)), ''),
                       g.against
                     )
            WHEN g.voucher_subtype = 'Depreciation Entry'
                THEN TRIM(SUBSTRING_INDEX(COALESCE(g.remarks,''), 'Note:', 1))
            WHEN g.voucher_type = 'Payment Entry'
                THEN COALESCE(NULLIF(TRIM(pe.remarks), ''), g.against)
            WHEN g.remarks LIKE '%%received from%%'
                THEN TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(COALESCE(g.remarks,''), 'Transaction reference no', 1), 'received from ', -1))
            WHEN g.remarks LIKE '%%PAY PRD%%'
                THEN 'PAYROLL'
            ELSE g.against
        END AS particulars,
        NULL AS beginning_balance,
        g.debit AS debit,
        g.credit AS credit,
        SUM(g.debit)  OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx) AS net_debit,
        SUM(g.credit) OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx) AS net_credit,
        CASE
            WHEN (
                COALESCE((
                    SELECT SUM(gle_bb.debit - gle_bb.credit)
                    FROM `tabGL Entry` gle_bb
                    WHERE gle_bb.docstatus = 1
                      AND IFNULL(gle_bb.is_cancelled, 0) = 0
                      AND gle_bb.company = %(company)s
                      AND gle_bb.posting_date < %(from_date)s
                      AND gle_bb.account = g.account
                ), 0)
                + SUM(g.debit)  OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
                - SUM(g.credit) OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
            ) > 0
            THEN (
                COALESCE((
                    SELECT SUM(gle_bb.debit - gle_bb.credit)
                    FROM `tabGL Entry` gle_bb
                    WHERE gle_bb.docstatus = 1
                      AND IFNULL(gle_bb.is_cancelled, 0) = 0
                      AND gle_bb.company = %(company)s
                      AND gle_bb.posting_date < %(from_date)s
                      AND gle_bb.account = g.account
                ), 0)
                + SUM(g.debit)  OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
                - SUM(g.credit) OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
            )
            ELSE 0
        END AS balance_debit,
        CASE
            WHEN (
                COALESCE((
                    SELECT SUM(gle_bb.debit - gle_bb.credit)
                    FROM `tabGL Entry` gle_bb
                    WHERE gle_bb.docstatus = 1
                      AND IFNULL(gle_bb.is_cancelled, 0) = 0
                      AND gle_bb.company = %(company)s
                      AND gle_bb.posting_date < %(from_date)s
                      AND gle_bb.account = g.account
                ), 0)
                + SUM(g.debit)  OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
                - SUM(g.credit) OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
            ) < 0
            THEN ABS(
                COALESCE((
                    SELECT SUM(gle_bb.debit - gle_bb.credit)
                    FROM `tabGL Entry` gle_bb
                    WHERE gle_bb.docstatus = 1
                      AND IFNULL(gle_bb.is_cancelled, 0) = 0
                      AND gle_bb.company = %(company)s
                      AND gle_bb.posting_date < %(from_date)s
                      AND gle_bb.account = g.account
                ), 0)
                + SUM(g.debit)  OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
                - SUM(g.credit) OVER (PARTITION BY g.account ORDER BY g.posting_date, g.voucher_no, g.idx)
            )
            ELSE 0
        END AS balance_credit,
        CASE WHEN IFNULL(g.is_cancelled, 0) = 1 THEN 'Cancelled' ELSE 'Posted' END AS status,
        g.owner AS owner,
        g.creation AS creation,
        g.modified_by AS modified_by,
        g.modified AS modified,
        CONCAT(
            g.account,
            '-2-',
            COALESCE(SUBSTRING_INDEX(g.cost_center, ' - ', 1), LEFT(g.remarks, 2), 'ZZ'),
            '-',
            DATE_FORMAT(g.posting_date, '%%Y%%m%%d'),
            '-',
            LPAD(g.idx, 5, '0')
        ) AS sort_order,
        COALESCE(SUBSTRING_INDEX(g.cost_center, ' - ', 1), LEFT(g.remarks, 2)) AS dept_code
    FROM `tabGL Entry` g
    LEFT JOIN `tabAccount` acc
           ON acc.name = g.account
          AND acc.company = %(company)s
    LEFT JOIN `tabJournal Entry Account` jea
           ON jea.parent = g.voucher_no
          AND jea.name   = g.voucher_detail_no
    LEFT JOIN `tabCustomer` cust_je
           ON cust_je.name = COALESCE(g.party, jea.party)
          AND COALESCE(g.party_type, jea.party_type) = 'Customer'
          AND g.voucher_type = 'Journal Entry'
    LEFT JOIN `tabSupplier` supp_je
           ON supp_je.name = COALESCE(g.party, jea.party)
          AND COALESCE(g.party_type, jea.party_type) = 'Supplier'
          AND g.voucher_type = 'Journal Entry'
    LEFT JOIN `tabEmployee` emp_je
           ON emp_je.name = COALESCE(g.party, jea.party)
          AND COALESCE(g.party_type, jea.party_type) = 'Employee'
          AND g.voucher_type = 'Journal Entry'
    LEFT JOIN `tabPayment Entry` pe ON pe.name = g.voucher_no AND g.voucher_type = 'Payment Entry'
    LEFT JOIN (
        SELECT parent, GROUP_CONCAT(name ORDER BY idx SEPARATOR '; ') AS ref_names
        FROM `tabPayment Entry Reference`
        GROUP BY parent
    ) per ON per.parent = g.voucher_no AND g.voucher_type = 'Payment Entry'
    LEFT JOIN `tabJournal Entry`    je ON je.name = g.voucher_no AND g.voucher_type = 'Journal Entry'
    LEFT JOIN `tabSales Invoice`    si ON si.name = g.voucher_no AND g.voucher_type = 'Sales Invoice'
    LEFT JOIN `tabPurchase Invoice` pi ON pi.name = g.voucher_no AND g.voucher_type = 'Purchase Invoice'
    LEFT JOIN `tabPurchase Receipt` pr ON pr.name = g.voucher_no AND g.voucher_type = 'Purchase Receipt'
    LEFT JOIN `tabStock Reconciliation` sr
           ON sr.name = g.voucher_no AND g.voucher_type = 'Stock Reconciliation'

    /* ---- Purchase Invoice items for Pay ---- */
    LEFT JOIN (
        SELECT
            per2.parent AS pe_name,
            GROUP_CONCAT(
                DISTINCT NULLIF(TRIM(pii.description), '')
                ORDER BY pii.idx
                SEPARATOR '; '
            ) AS description
        FROM `tabPayment Entry Reference` per2
        JOIN `tabPurchase Invoice Item` pii
          ON pii.parent = per2.reference_name
        WHERE per2.reference_doctype = 'Purchase Invoice'
          AND IFNULL(pii.description, '') <> ''
        GROUP BY per2.parent
    ) pi_items ON pi_items.pe_name = g.voucher_no AND g.voucher_type = 'Payment Entry'

    /* ---- Sales Invoice items for Receive ---- */
    LEFT JOIN (
        SELECT
            per2.parent AS pe_name,
            GROUP_CONCAT(
                DISTINCT NULLIF(TRIM(sii.description), '')
                ORDER BY sii.idx
                SEPARATOR '; '
            ) AS description
        FROM `tabPayment Entry Reference` per2
        JOIN `tabSales Invoice Item` sii
          ON sii.parent = per2.reference_name
        WHERE per2.reference_doctype = 'Sales Invoice'
          AND IFNULL(sii.description, '') <> ''
        GROUP BY per2.parent
    ) si_items ON si_items.pe_name = g.voucher_no AND g.voucher_type = 'Payment Entry'

    /* ---- Journal Entry Account user_remark for Pay referencing JE ---- */
    LEFT JOIN (
        SELECT
            per2.parent AS pe_name,
            GROUP_CONCAT(
                DISTINCT NULLIF(TRIM(jea2.user_remark), '')
                ORDER BY jea2.idx
                SEPARATOR '; '
            ) AS user_remark
        FROM `tabPayment Entry Reference` per2
        JOIN `tabJournal Entry Account` jea2
          ON jea2.parent = per2.reference_name
        WHERE per2.reference_doctype = 'Journal Entry'
          AND IFNULL(jea2.user_remark, '') <> ''
        GROUP BY per2.parent
    ) je_items ON je_items.pe_name = g.voucher_no AND g.voucher_type = 'Payment Entry'

    WHERE g.docstatus = 1
      AND (
        COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
        OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(g.is_cancelled, 0) = 0)
        OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(g.is_cancelled, 0) = 1)
      )
      AND g.company = %(company)s
      AND g.posting_date BETWEEN %(from_date)s AND %(to_date)s
      AND g.account IN (SELECT account FROM accounts_in_scope)

    UNION ALL

    /* ======== DEPARTMENT SUBTOTAL ROWS ======== */
    SELECT
        NULL AS account,
        NULL AS cost_center,
        NULL AS transaction_date,
        NULL AS doc_type,
        NULL AS doc_type_label,
        NULL AS doc_no,
        NULL AS reference_no,
        NULL AS party,
        CONCAT(
            '<b>',
            TRIM(TRAILING CONCAT(' - ', SUBSTRING_INDEX(g.cost_center, ' - ', -1)) FROM g.cost_center),
            ' SUBTOTAL</b>'
        ) AS particulars,
        NULL AS beginning_balance,
        SUM(g.debit) AS debit,
        SUM(g.credit) AS credit,
        CASE WHEN SUM(g.debit) - SUM(g.credit) > 0 THEN SUM(g.debit) - SUM(g.credit) ELSE 0 END AS net_debit,
        CASE WHEN SUM(g.credit) - SUM(g.debit) > 0 THEN SUM(g.credit) - SUM(g.debit) ELSE 0 END AS net_credit,
        NULL AS balance_debit,
        NULL AS balance_credit,
        NULL AS status,
        NULL AS owner,
        NULL AS creation,
        NULL AS modified_by,
        NULL AS modified,
        CONCAT(
            g.account,
            '-2-',
            COALESCE(SUBSTRING_INDEX(g.cost_center, ' - ', 1), LEFT(g.remarks, 2)),
            '-99999999-99999'
        ) AS sort_order,
        COALESCE(SUBSTRING_INDEX(g.cost_center, ' - ', 1), LEFT(g.remarks, 2)) AS dept_code
    FROM `tabGL Entry` g
    WHERE g.docstatus = 1
      AND (
        COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
        OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(g.is_cancelled, 0) = 0)
        OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(g.is_cancelled, 0) = 1)
      )
      AND g.company = %(company)s
      AND g.posting_date BETWEEN %(from_date)s AND %(to_date)s
      AND %(account)s = 'Cost of Sales Accounts'
      AND EXISTS (
        SELECT 1 FROM `tabAccount` a
        WHERE a.name = g.account
          AND a.company = %(company)s
          AND a.account_type = 'Cost of Goods Sold'
      )
    GROUP BY
        g.account,
        TRIM(TRAILING CONCAT(' - ', SUBSTRING_INDEX(g.cost_center, ' - ', -1)) FROM g.cost_center)

    UNION ALL

    /* ======== ACCOUNT TOTAL ROW ======== */
    SELECT
        NULL AS account,
        NULL AS cost_center,
        NULL AS transaction_date,
        NULL AS doc_type,
        NULL AS doc_type_label,
        NULL AS doc_no,
        NULL AS reference_no,
        NULL AS party,
        '<b>ACCOUNT TOTAL:</b>' AS particulars,
        COALESCE((
            SELECT SUM(gle_bb.debit - gle_bb.credit)
            FROM `tabGL Entry` gle_bb
            WHERE gle_bb.docstatus = 1
              AND IFNULL(gle_bb.is_cancelled, 0) = 0
              AND gle_bb.company = %(company)s
              AND gle_bb.posting_date < %(from_date)s
              AND gle_bb.account = ais.account
        ), 0) AS beginning_balance,
        COALESCE(SUM(gle.debit), 0) AS debit,
        COALESCE(SUM(gle.credit), 0) AS credit,
        CASE WHEN COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) > 0
             THEN COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) ELSE 0 END AS net_debit,
        CASE WHEN COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) > 0
             THEN COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) ELSE 0 END AS net_credit,
        CASE
          WHEN (
            COALESCE((
              SELECT SUM(gle_bb.debit - gle_bb.credit)
              FROM `tabGL Entry` gle_bb
              WHERE gle_bb.docstatus = 1
                AND IFNULL(gle_bb.is_cancelled, 0) = 0
                AND gle_bb.company = %(company)s
                AND gle_bb.posting_date < %(from_date)s
                AND gle_bb.account = ais.account
            ), 0)
            + COALESCE(SUM(gle.debit), 0) - COALESCE(SUM(gle.credit), 0)
          ) > 0
          THEN (
            COALESCE((
              SELECT SUM(gle_bb.debit - gle_bb.credit)
              FROM `tabGL Entry` gle_bb
              WHERE gle_bb.docstatus = 1
                AND IFNULL(gle_bb.is_cancelled, 0) = 0
                AND gle_bb.company = %(company)s
                AND gle_bb.posting_date < %(from_date)s
                AND gle_bb.account = ais.account
            ), 0)
            + COALESCE(SUM(gle.debit), 0) - COALESCE(SUM(gle.credit), 0)
          )
          ELSE 0
        END AS balance_debit,
        CASE
          WHEN (
            COALESCE((
              SELECT SUM(gle_bb.debit - gle_bb.credit)
              FROM `tabGL Entry` gle_bb
              WHERE gle_bb.docstatus = 1
                AND IFNULL(gle_bb.is_cancelled, 0) = 0
                AND gle_bb.company = %(company)s
                AND gle_bb.posting_date < %(from_date)s
                AND gle_bb.account = ais.account
            ), 0)
            + COALESCE(SUM(gle.debit), 0) - COALESCE(SUM(gle.credit), 0)
          ) < 0
          THEN ABS(
            COALESCE((
              SELECT SUM(gle_bb.debit - gle_bb.credit)
              FROM `tabGL Entry` gle_bb
              WHERE gle_bb.docstatus = 1
                AND IFNULL(gle_bb.is_cancelled, 0) = 0
                AND gle_bb.company = %(company)s
                AND gle_bb.posting_date < %(from_date)s
                AND gle_bb.account = ais.account
            ), 0)
            + COALESCE(SUM(gle.debit), 0) - COALESCE(SUM(gle.credit), 0)
          )
          ELSE 0
        END AS balance_credit,
        NULL AS status,
        NULL AS owner,
        NULL AS creation,
        NULL AS modified_by,
        NULL AS modified,
        CONCAT(ais.account, '-3') AS sort_order,
        NULL AS dept_code
    FROM accounts_in_scope ais
    LEFT JOIN `tabGL Entry` gle
      ON gle.account = ais.account
     AND gle.docstatus = 1
     AND (
       COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
       OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(gle.is_cancelled, 0) = 0)
       OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(gle.is_cancelled, 0) = 1)
     )
     AND gle.company = %(company)s
     AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
    GROUP BY ais.account

    UNION ALL

    /* ======== BLANK SEPARATOR ROW ======== */
    SELECT
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        '' AS particulars,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL AS status,
        NULL AS owner,
        NULL AS creation,
        NULL AS modified_by,
        NULL AS modified,
        CONCAT(ais.account, '-4') AS sort_order,
        NULL AS dept_code
    FROM accounts_in_scope ais

    UNION ALL

    /* ======== GRAND TOTAL ROW (all accounts in scope) ======== */
    SELECT
        NULL AS account,
        NULL AS cost_center,
        NULL AS transaction_date,
        NULL AS doc_type,
        NULL AS doc_type_label,
        NULL AS doc_no,
        NULL AS reference_no,
        NULL AS party,
        '<b>GRAND TOTAL:</b>' AS particulars,
        /* Beginning Balance grand total: sum of each account's pre-period net balance */
        COALESCE((
          SELECT SUM(gle_bb.debit - gle_bb.credit)
          FROM `tabGL Entry` gle_bb
          WHERE gle_bb.docstatus = 1
            AND IFNULL(gle_bb.is_cancelled, 0) = 0
            AND gle_bb.company = %(company)s
            AND gle_bb.posting_date < %(from_date)s
            AND gle_bb.account IN (SELECT account FROM accounts_in_scope)
        ), 0) AS beginning_balance,
        COALESCE(SUM(gle.debit), 0) AS debit,
        COALESCE(SUM(gle.credit), 0) AS credit,
        CASE WHEN COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) > 0
             THEN COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) ELSE 0 END AS net_debit,
        CASE WHEN COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) > 0
             THEN COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) ELSE 0 END AS net_credit,
        /*
          balance_debit grand total:
            For each account, compute ending balance = BB + period net.
            Sum only the positive ending balances (debit-normal accounts).
        */
        COALESCE((
          SELECT SUM(acct_end.ending_balance)
          FROM (
            SELECT
              ais2.account,
              COALESCE((
                SELECT SUM(bb.debit - bb.credit)
                FROM `tabGL Entry` bb
                WHERE bb.docstatus = 1
                  AND IFNULL(bb.is_cancelled, 0) = 0
                  AND bb.company = %(company)s
                  AND bb.posting_date < %(from_date)s
                  AND bb.account = ais2.account
              ), 0)
              + COALESCE((
                SELECT SUM(pd.debit) - SUM(pd.credit)
                FROM `tabGL Entry` pd
                WHERE pd.docstatus = 1
                  AND (
                    COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
                    OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(pd.is_cancelled, 0) = 0)
                    OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(pd.is_cancelled, 0) = 1)
                  )
                  AND pd.company = %(company)s
                  AND pd.posting_date BETWEEN %(from_date)s AND %(to_date)s
                  AND pd.account = ais2.account
              ), 0) AS ending_balance
            FROM accounts_in_scope ais2
          ) acct_end
          WHERE acct_end.ending_balance > 0
        ), 0) AS balance_debit,
        /*
          balance_credit grand total:
            For each account, compute ending balance = BB + period net.
            Sum ABS of the negative ending balances (credit-normal accounts).
        */
        COALESCE((
          SELECT SUM(ABS(acct_end.ending_balance))
          FROM (
            SELECT
              ais2.account,
              COALESCE((
                SELECT SUM(bb.debit - bb.credit)
                FROM `tabGL Entry` bb
                WHERE bb.docstatus = 1
                  AND IFNULL(bb.is_cancelled, 0) = 0
                  AND bb.company = %(company)s
                  AND bb.posting_date < %(from_date)s
                  AND bb.account = ais2.account
              ), 0)
              + COALESCE((
                SELECT SUM(pd.debit) - SUM(pd.credit)
                FROM `tabGL Entry` pd
                WHERE pd.docstatus = 1
                  AND (
                    COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
                    OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(pd.is_cancelled, 0) = 0)
                    OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(pd.is_cancelled, 0) = 1)
                  )
                  AND pd.company = %(company)s
                  AND pd.posting_date BETWEEN %(from_date)s AND %(to_date)s
                  AND pd.account = ais2.account
              ), 0) AS ending_balance
            FROM accounts_in_scope ais2
          ) acct_end
          WHERE acct_end.ending_balance < 0
        ), 0) AS balance_credit,
        NULL AS status,
        NULL AS owner,
        NULL AS creation,
        NULL AS modified_by,
        NULL AS modified,
        'ZZZZZZZZZZ-GRAND-TOTAL' AS sort_order,
        NULL AS dept_code
    FROM accounts_in_scope ais
    LEFT JOIN `tabGL Entry` gle
      ON gle.account = ais.account
     AND gle.docstatus = 1
     AND (
       COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'All Transactions'
       OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Posted Transactions'    AND IFNULL(gle.is_cancelled, 0) = 0)
       OR (COALESCE(NULLIF(%(status)s, ''), 'Posted Transactions') = 'Cancelled Transactions' AND IFNULL(gle.is_cancelled, 0) = 1)
     )
     AND gle.company = %(company)s
     AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s

) combined
ORDER BY (sort_order = 'ZZZZZZZZZZ-GRAND-TOTAL'), sort_order, transaction_date;
"""

	return frappe.db.sql(sql, filters, as_dict=True)