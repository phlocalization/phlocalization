import frappe


def execute(filters=None):
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
    return [
        {"fieldname": "doc_type", "label": "Document Type", "fieldtype": "Data", "width": 120},
        {"fieldname": "doc_no_html", "label": "Document No", "fieldtype": "HTML", "width": 140},
        {"fieldname": "transaction_date", "label": "Transaction Date", "fieldtype": "Date", "width": 100},
        {"fieldname": "Vendor_name", "label": "Vendor Name", "fieldtype": "Link", "options": "Customer", "width": 220},
        {"fieldname": "bank_account", "label": "Bank Account", "fieldtype": "Data", "width": 260},
        {"fieldname": "paid_amount", "label": "Paid Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "reference_html", "label": "Reference", "fieldtype": "HTML", "width": 120},
        {"fieldname": "reference_invoice", "label": "Reference Invoice", "fieldtype": "Data", "width": 200},
        {"fieldname": "reference_date", "label": "Reference Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "account", "label": "Account", "fieldtype": "Data", "width": 280},
        {"fieldname": "cost_center", "label": "Cost Center", "fieldtype": "Link", "options": "Cost Center", "width": 150},
        {"fieldname": "description", "label": "Description", "fieldtype": "Data", "width": 300},
        {"fieldname": "amount", "label": "Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "applied", "label": "Applied", "fieldtype": "Currency", "width": 120}
    ]


def get_data(filters):
    query = """
    SELECT
        doc_type,
        doc_no_html,
        transaction_date,
        Vendor_name,
        bank_account,
        paid_amount,
        reference_html,
        reference_invoice,
        reference_date,
        account,
        cost_center,
        description,
        amount,
        applied
    FROM (

        /* ======================= DETAIL ROWS ======================= */
        SELECT
            /* 1 */ CASE
                    WHEN gle.voucher_type = 'Journal Entry' THEN (
                        SELECT je.cheque_date FROM `tabJournal Entry` je WHERE je.name = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Sales Invoice' THEN (
                        SELECT si.posting_date FROM `tabSales Invoice` si WHERE si.name = gle.voucher_no
                    )
                    ELSE gle.posting_date
                    END AS transaction_date,

            /* 2 */ CASE
                    WHEN gle.voucher_type = 'Payment Entry' THEN (
                        SELECT CONCAT(gle.voucher_type, ' - ', pe.payment_type)
                        FROM `tabPayment Entry` pe WHERE pe.name = gle.voucher_no
                    )
                    ELSE gle.voucher_type
                    END AS doc_type,

            /* 3 */ CONCAT('<a href="/app/', LOWER(REPLACE(gle.voucher_type, ' ', '-')), '/', gle.voucher_no, '">', gle.voucher_no, '</a>') AS doc_no_html,

            /* 4 */ (
                    SELECT CONCAT(a2.account_number, ' - ', a2.account_name)
                    FROM `tabPayment Entry` pe2
                    JOIN `tabAccount` a2 ON a2.name = pe2.paid_from
                    WHERE pe2.name = gle.voucher_no
                ) AS bank_account,

            /* 5 */ gle.party AS Vendor_name,

            /* 6 */ CASE
                    WHEN gle.voucher_type = 'Sales Invoice' THEN (
                        SELECT COALESCE(si.remarks, '') FROM `tabSales Invoice` si WHERE si.name = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Journal Entry' THEN (
                        SELECT COALESCE(je.cheque_no, '') FROM `tabJournal Entry` je WHERE je.name = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Payment Entry' THEN (
                        SELECT COALESCE(pe.reference_no, '') FROM `tabPayment Entry` pe WHERE pe.name = gle.voucher_no
                    )
                    ELSE COALESCE(gle.against_voucher, '')
                    END AS reference_html,

            /* 7 */ CONCAT(a.account_number, ' - ', a.account_name) AS account,
            /* 8 */ COALESCE(gle.cost_center, '') AS cost_center,

            /* 9 */ (
                    SELECT COALESCE(pe.paid_amount, 0)
                    FROM `tabPayment Entry` pe
                    WHERE pe.name = gle.voucher_no
                ) AS paid_amount,

            /* 10 */ CASE
                    WHEN a.account_number LIKE '1203%%' OR a.account_number LIKE '1205%%' OR a.account_number LIKE '1214%%' THEN (
                        SELECT COALESCE(pe.reference_no, '') FROM `tabPayment Entry` pe WHERE pe.name = gle.voucher_no
                    )
                    WHEN a.account_number LIKE '1301%%' THEN (
                        /* custom_remarks → reference_name WHERE reference_doctype = Journal Entry */
                        SELECT GROUP_CONCAT(DISTINCT per.reference_name SEPARATOR '; ')
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                        AND per.reference_doctype = 'Journal Entry'
                        AND per.reference_name IS NOT NULL
                        AND per.reference_name != ''
                    )
                    WHEN a.account_number LIKE '1604%%' THEN COALESCE(ped.description, '')
                    WHEN gle.voucher_type = 'Sales Invoice' THEN (
                        SELECT GROUP_CONCAT(DISTINCT sii.description SEPARATOR '; ')
                        FROM `tabSales Invoice Item` sii
                        WHERE sii.parent = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Journal Entry' THEN (
                        SELECT COALESCE(jea.user_remark, '')
                        FROM `tabJournal Entry Account` jea
                        WHERE jea.parent = gle.voucher_no
                        AND jea.account = gle.account
                        AND COALESCE(jea.debit, 0)  = COALESCE(gle.debit, 0)
                        AND COALESCE(jea.credit, 0) = COALESCE(gle.credit, 0)
                        LIMIT 1
                    )
                    ELSE COALESCE(gle.remarks, '')
                    END AS description,

            /* 11 */ CASE
                    WHEN %(status)s = 'Cancelled Only'
                    OR (%(status)s = 'All' AND gle.is_cancelled = 1)
                    THEN (
                        /* cancelled: reference_name is already clean, no strip needed */
                        SELECT per.reference_name
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                        AND per.reference_doctype = 'Journal Entry'
                        AND per.reference_name = gle.against_voucher
                        LIMIT 1
                    )
                    ELSE (
                        /* posted: show JE ID from reference_name */
                        SELECT per.reference_name
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                        AND per.reference_doctype = 'Journal Entry'
                        AND per.reference_name = gle.against_voucher
                        LIMIT 1
                    )
                    END AS reference_invoice,

            /* 12 */ CASE
                    WHEN gle.voucher_type = 'Journal Entry' THEN (
                        SELECT je.cheque_date FROM `tabJournal Entry` je WHERE je.name = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Payment Entry' THEN (
                        SELECT pe.reference_date FROM `tabPayment Entry` pe WHERE pe.name = gle.voucher_no
                    )
                    WHEN gle.voucher_type = 'Sales Invoice' THEN (
                        SELECT si.posting_date FROM `tabSales Invoice` si WHERE si.name = gle.voucher_no
                    )
                    ELSE gle.posting_date
                    END AS reference_date,

            /* 13 */ CASE
                    WHEN a.account_number LIKE '1604%%' THEN (
                        SELECT p2.allocated_amount
                        FROM `tabPayment Entry Reference` p2
                        WHERE p2.parent = gle.voucher_no
                        AND (
                            p2.reference_name = gle.against_voucher
                            OR (
                                /* custom_remarks → reference_name WHERE reference_doctype = Journal Entry */
                                p2.reference_doctype = 'Journal Entry'
                                AND p2.reference_name IS NOT NULL AND p2.reference_name != ''
                                AND ped.description IS NOT NULL
                                AND ped.description LIKE CONCAT('%%', p2.reference_name, '%%')
                            )
                        )
                        LIMIT 1
                    )
                    ELSE (
                        SELECT per.allocated_amount
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                        AND per.reference_name = gle.against_voucher
                        LIMIT 1
                    )
                    END AS amount,

            /* 14 */ CASE
                    WHEN a.account_number LIKE '1301%%' THEN (
                        SELECT per.allocated_amount
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                        AND per.reference_name = gle.against_voucher
                        LIMIT 1
                    )
                    WHEN a.account_number LIKE '1203%%' OR a.account_number LIKE '1205%%' THEN (
                        SELECT COALESCE(SUM(per.allocated_amount), 0)
                        FROM `tabPayment Entry Reference` per
                        WHERE per.parent = gle.voucher_no
                    )
                    WHEN a.account_number LIKE '1604%%' THEN COALESCE(ped.amount, 0) * -1
                    ELSE COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)
                    END AS applied,

            /* internal */ NULL AS ref_sort_key,

            /* internal */ CONCAT(
                    gle.posting_date, '-', gle.voucher_no, '-1-',
                    LPAD(
                        COALESCE(
                            CASE
                                WHEN a.account_number LIKE '1604%%' THEN (
                                    SELECT p2.idx
                                    FROM `tabPayment Entry Reference` p2
                                    WHERE p2.parent = gle.voucher_no
                                    AND (
                                        p2.reference_name = gle.against_voucher
                                        OR (
                                            /* custom_remarks → reference_name WHERE reference_doctype = Journal Entry */
                                            p2.reference_doctype = 'Journal Entry'
                                            AND p2.reference_name IS NOT NULL AND p2.reference_name != ''
                                            AND ped.description IS NOT NULL
                                            AND ped.description LIKE CONCAT('%%', p2.reference_name, '%%')
                                        )
                                    )
                                    LIMIT 1
                                )
                                ELSE (
                                    SELECT per.idx
                                    FROM `tabPayment Entry Reference` per
                                    WHERE per.parent = gle.voucher_no
                                    AND per.reference_name = gle.against_voucher
                                    LIMIT 1
                                )
                            END
                        , 99999), 5, '0'
                    ),
                    '-',
                    CASE
                        WHEN a.account_number LIKE '1301%%' THEN '01'
                        WHEN a.account_number LIKE '1604%%' THEN '02'
                        ELSE '99'
                    END,
                    '-', LPAD(gle.idx, 5, '0')
                ) AS sort_order

        FROM `tabGL Entry` gle
        JOIN `tabAccount` a ON a.name = gle.account
        LEFT JOIN `tabPayment Entry Deduction` ped
            ON ped.parent = gle.voucher_no
            AND ped.account = gle.account
        WHERE
            (
                %(status)s = 'All'
                OR (%(status)s = 'Cancelled Only' AND gle.is_cancelled = 1)
                OR (%(status)s = 'Posted Only'    AND gle.is_cancelled = 0)
            )
            AND gle.company = %(company)s
            AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND gle.voucher_type = 'Payment Entry'
            AND EXISTS (
                SELECT 1 FROM `tabPayment Entry` pe
                WHERE pe.name = gle.voucher_no AND pe.payment_type = 'Pay'
            )
            AND a.account_number NOT LIKE '1203%%'
            AND a.account_number NOT LIKE '1205%%'

        UNION ALL

/* ======================= SUBTOTAL ROWS ======================= */
        SELECT
            NULL AS transaction_date,
            '' AS doc_type,
            '' AS doc_no_html,
            '' AS bank_account,
            '' AS Vendor_name,
            '' AS reference_html,
            '' AS account,
            '' AS cost_center,
            NULL AS paid_amount,
            '<b>SUBTOTAL</b>' AS description,
            '' AS reference_invoice,
            NULL AS reference_date,

            /* amount = paid_amount of the voucher */
            MAX((
                SELECT COALESCE(pe.paid_amount, 0)
                FROM `tabPayment Entry` pe
                WHERE pe.name = gle.voucher_no
            )) AS amount,

            /* applied = sum of debit-credit across ALL accounts for this voucher */
            SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS applied,

            NULL AS ref_sort_key,
            CONCAT(gle.posting_date, '-', gle.voucher_no, '-2-0-00000') AS sort_order

        FROM `tabGL Entry` gle
        JOIN `tabAccount` a ON a.name = gle.account
        WHERE
            (
                %(status)s = 'All'
                OR (%(status)s = 'Cancelled Only' AND gle.is_cancelled = 1)
                OR (%(status)s = 'Posted Only'    AND gle.is_cancelled = 0)
            )
            AND gle.company = %(company)s
            AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND gle.voucher_type = 'Payment Entry'
            AND EXISTS (
                SELECT 1 FROM `tabPayment Entry` pe
                WHERE pe.name = gle.voucher_no AND pe.payment_type = 'Pay'
            )
        GROUP BY gle.posting_date, gle.voucher_no

        UNION ALL

        /* ======================= BLANK ROWS (after each transaction) ======================= */
        SELECT
            NULL AS transaction_date,
            '' AS doc_type,
            '' AS doc_no_html,
            '' AS bank_account,
            '' AS Vendor_name,
            '' AS reference_html,
            '' AS account,
            '' AS cost_center,
            NULL AS paid_amount,
            '' AS description,
            '' AS reference_invoice,
            NULL AS reference_date,
            NULL AS amount,
            NULL AS applied,
            NULL AS ref_sort_key,
            CONCAT(gle.posting_date, '-', gle.voucher_no, '-3-0-00000') AS sort_order

        FROM `tabGL Entry` gle
        JOIN `tabAccount` a ON a.name = gle.account
        WHERE
            (
                %(status)s = 'All'
                OR (%(status)s = 'Cancelled Only' AND gle.is_cancelled = 1)
                OR (%(status)s = 'Posted Only'    AND gle.is_cancelled = 0)
            )
            AND gle.company = %(company)s
            AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND gle.voucher_type = 'Payment Entry'
            AND EXISTS (
                SELECT 1 FROM `tabPayment Entry` pe
                WHERE pe.name = gle.voucher_no AND pe.payment_type = 'Pay'
            )
        GROUP BY gle.posting_date, gle.voucher_no

        UNION ALL

        /* ======================= GRAND TOTAL ROW ======================= */
        SELECT
            NULL AS transaction_date,
            '' AS doc_type,
            '' AS doc_no_html,
            '' AS bank_account,
            '' AS Vendor_name,
            '' AS reference_html,
            '' AS account,
            '' AS cost_center,
            NULL AS paid_amount,
            '<b>GRAND TOTAL</b>' AS description,
            '' AS reference_invoice,
            NULL AS reference_date,
            SUM(sub_amount) AS amount,
            SUM(sub_applied) AS applied,
            NULL AS ref_sort_key,
            'ZZZZ-GRAND-TOTAL' AS sort_order
        FROM (
            SELECT
                gle.voucher_no,
                MAX((
                    SELECT COALESCE(pe.paid_amount, 0)
                    FROM `tabPayment Entry` pe
                    WHERE pe.name = gle.voucher_no
                )) AS sub_amount,
                SUM(COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)) AS sub_applied
            FROM `tabGL Entry` gle
            JOIN `tabAccount` a ON a.name = gle.account
            WHERE
                (
                    %(status)s = 'All'
                    OR (%(status)s = 'Cancelled Only' AND gle.is_cancelled = 1)
                    OR (%(status)s = 'Posted Only'    AND gle.is_cancelled = 0)
                )
                AND gle.company = %(company)s
                AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND gle.voucher_type = 'Payment Entry'
                AND EXISTS (
                    SELECT 1 FROM `tabPayment Entry` pe
                    WHERE pe.name = gle.voucher_no AND pe.payment_type = 'Pay'
                )
            GROUP BY gle.voucher_no
        ) AS _grand_total_sub

    ) AS combined_results
    ORDER BY sort_order
    """
    return frappe.db.sql(query, filters, as_dict=True)