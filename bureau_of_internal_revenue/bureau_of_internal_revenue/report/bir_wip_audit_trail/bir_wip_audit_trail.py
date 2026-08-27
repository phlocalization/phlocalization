# Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""
	Report entry point. Builds columns and fetches data for the given filters.
	Returns (columns, data) for Frappe's query report framework.
	"""
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "DOC TYPE", "fieldname": "DOC TYPE", "fieldtype": "Data", "width": 130},
		{"label": "DOC NO", "fieldname": "DOC NO", "fieldtype": "Data", "width": 130},
		{"label": "REFERENCE", "fieldname": "REFERENCE", "fieldtype": "Data", "width": 160},
		{"label": "TRAN DATE", "fieldname": "TRAN DATE", "fieldtype": "Date", "width": 100},
		{"label": "PAYEE/RECEIVED FROM", "fieldname": "PAYEE/RECEIVED FROM", "fieldtype": "Data", "width": 180},
		{"label": "PARTICULARS", "fieldname": "PARTICULARS", "fieldtype": "Data", "width": 260},
		{"label": "DEBIT", "fieldname": "DEBIT", "fieldtype": "Data", "width": 120, "align": "right"},
		{"label": "CREDIT", "fieldname": "CREDIT", "fieldtype": "Data", "width": 120, "align": "right"},
		{"label": "NET CHANGE", "fieldname": "NET CHANGE", "fieldtype": "Data", "width": 120, "align": "right"},
		{"label": "JO NUMBER", "fieldname": "JO NUMBER", "fieldtype": "Data", "width": 130},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": "Created On", "fieldname": "CREATION", "fieldtype": "Datetime", "width": 150},
		{"label": "Modified By", "fieldname": "MODIFIED BY", "fieldtype": "Data", "width": 150},
		{"label": "Modified On", "fieldname": "MODIFIED", "fieldtype": "Datetime", "width": 150},
		{"label": "Owner", "fieldname": "OWNER", "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	"""
	Run the SQL query aggregating Stock Entries, Journal Entries, and Purchase
	Invoices into a GL-style ledger with per-JO subtotals and a report-wide footer.
	Takes filters (company, from_date, to_date, status); returns rows.
	"""
	query = """
		SELECT
			r.doc_type            AS `DOC TYPE`,
			r.doc_no_field        AS `DOC NO`,
			r.reference           AS `REFERENCE`,
			r.tran_date           AS `TRAN DATE`,
			r.payee_received_from AS `PAYEE/RECEIVED FROM`,
			r.particulars         AS `PARTICULARS`,
			CASE WHEN r.debit IS NOT NULL THEN
				CASE WHEN r.section_order IN (4,6,7)
					  OR (r.block_order = 2 AND r.section_order IN (3,4,5))
					 THEN CONCAT('<b>', FORMAT(r.debit, 2), '</b>')
					 ELSE FORMAT(r.debit, 2)
				END
			END AS `DEBIT`,
			CASE WHEN r.credit IS NOT NULL THEN
				CASE WHEN r.section_order IN (4,6,7)
					  OR (r.block_order = 2 AND r.section_order IN (3,4,5))
					 THEN CONCAT('<b>', FORMAT(r.credit, 2), '</b>')
					 ELSE FORMAT(r.credit, 2)
				END
			END AS `CREDIT`,
			CASE WHEN r.net_change IS NOT NULL THEN
				CASE WHEN r.section_order IN (4,6,7)
					  OR (r.block_order = 2 AND r.section_order IN (3,4,5))
					 THEN CONCAT('<b>', FORMAT(r.net_change, 2), '</b>')
					 ELSE FORMAT(r.net_change, 2)
				END
			END AS `NET CHANGE`,
			CASE WHEN r.block_order = 1 AND r.section_order IN (8,9) THEN NULL
				 ELSE r.jo_number
			END AS `JO NUMBER`,
			r.status_label AS `status`,
			r.creation     AS `CREATION`,
			r.modified_by  AS `MODIFIED BY`,
			r.modified     AS `MODIFIED`,
			r.owner        AS `OWNER`
		FROM (
			/* ══════════════════════════════════════════════════════
			   §1  STOCK DETAIL ROWS
			══════════════════════════════════════════════════════ */
			SELECT
				1 AS block_order, j.jo_number, 1 AS section_order,
				s.tran_date, s.doc_no_field, s.doc_type, s.reference,
				s.payee_received_from, s.particulars,
				s.debit, s.credit, s.net_change, s.status_label AS status_label,
				s.creation, s.modified_by, s.modified, s.owner
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se
					JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project AS jo_number
					FROM `tabJournal Entry` je
					JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND jea.project IS NOT NULL
					  AND jea.account LIKE '1521%%'
					UNION
					SELECT pii.project AS jo_number
					FROM `tabPurchase Invoice Item` pii
					JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND pii.expense_account LIKE '1521%%'
				) all_jo_src WHERE jo_number IS NOT NULL
			) j
			JOIN (
				SELECT
					COALESCE(sed.project, se.project) AS jo_number,
					se.posting_date AS tran_date,
					se.name AS doc_no_field,
					CASE
						WHEN se.stock_entry_type = 'Material Transfer' THEN
							CASE WHEN COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN 'MR' ELSE 'MRS' END
						ELSE se.stock_entry_type
					END AS doc_type,
					(SELECT p.customer FROM `tabProject` p
					 WHERE p.name = COALESCE(sed.project, se.project) LIMIT 1) AS reference,
					'INVENTORY ENTRY TO GL' AS payee_received_from,
					CONCAT('Item#', sed.item_code, ': ', COALESCE(sed.description, ''), ' - ', sed.qty, ' PC') AS particulars,
					CASE
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN sed.amount
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') NOT LIKE 'Stores%%' THEN 0
						ELSE sed.amount
					END AS debit,
					CASE
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN 0
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') NOT LIKE 'Stores%%' THEN sed.amount
						ELSE 0
					END AS credit,
					CASE
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN sed.amount
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') NOT LIKE 'Stores%%' THEN -sed.amount
						ELSE sed.amount
					END AS net_change,
					CASE WHEN se.docstatus = 2 THEN 'Cancelled' ELSE 'Posted' END AS status_label,
					se.creation AS creation, se.modified_by AS modified_by,
					se.modified AS modified, se.owner AS owner
				FROM `tabStock Entry` se
				JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				WHERE se.docstatus IN (1, 2)
				  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
				  AND se.company = %(company)s
				  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND COALESCE(sed.project, se.project) IS NOT NULL
			) s ON s.jo_number = j.jo_number
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §2  MR/MRS TOTAL per JO
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 2,
				   NULL, NULL, '', NULL,
				   'INVENTORY ENTRY TO GL', 'MR/MRS TOTAL:',
				   m.net_change, NULL, NULL, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			JOIN (
				SELECT
					COALESCE(sed.project, se.project) AS jo_number,
					SUM(CASE
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
						ELSE ROUND(sed.amount, 2)
					END) AS net_change
				FROM `tabStock Entry` se
				JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				WHERE se.docstatus = 1
				  AND se.company = %(company)s
				  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND COALESCE(sed.project, se.project) IS NOT NULL
				  AND CASE
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') LIKE 'Stores%%' THEN 'MR'
						WHEN se.stock_entry_type = 'Material Transfer'
						 AND COALESCE(sed.s_warehouse, '') NOT LIKE 'Stores%%' THEN 'MRS'
						ELSE 'OTHER'
					  END IN ('MR','MRS')
				GROUP BY COALESCE(sed.project, se.project)
			) m ON m.jo_number = j.jo_number
			WHERE COALESCE(m.net_change, 0) <> 0
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §3  OVER ALL TOTAL per JO  (Stock Entries only)
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 4,
				   NULL, NULL, '', NULL,
				   '<b>INVENTORY ENTRY TO GL</b>', '<b>OVER ALL TOTAL:</b>',
				   COALESCE(m.net_change, 0),
				   NULL,
				   COALESCE(s.net_change, 0),
				   NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			LEFT JOIN (
				SELECT COALESCE(sed.project, se.project) AS jo_number,
					SUM(CASE
						WHEN se.stock_entry_type = 'Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
						WHEN se.stock_entry_type = 'Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
						ELSE ROUND(sed.amount, 2) END) AS net_change
				FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				WHERE se.docstatus = 1 AND se.company = %(company)s
				  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND COALESCE(sed.project, se.project) IS NOT NULL
				  AND CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 'MR'
						   WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 'MRS'
						   ELSE 'OTHER' END IN ('MR','MRS')
				GROUP BY COALESCE(sed.project, se.project)
			) m ON m.jo_number = j.jo_number
			LEFT JOIN (
				SELECT jo_number, SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 0
							 ELSE ROUND(sed.amount, 2) END AS debit,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 0
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 ELSE 0 END AS credit,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
							 ELSE ROUND(sed.amount, 2) END AS net_change
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
					WHERE se.docstatus=1 AND se.company=%(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
				) sx GROUP BY jo_number
			) s ON s.jo_number = j.jo_number
			WHERE COALESCE(m.net_change,0)<>0 OR COALESCE(s.net_change,0)<>0
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §5  JE/PI DETAIL ROWS
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 5,
				   c.tran_date, c.doc_no_field, c.doc_type, c.reference,
				   c.payee_received_from, c.particulars,
				   c.debit, c.credit, c.net_change, c.status_label,
				   c.creation, c.modified_by, c.modified, c.owner
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			JOIN (
				SELECT jea.project AS jo_number,
					je.posting_date AS tran_date,
					REPLACE(REPLACE(REPLACE(je.name,'ACC-JV-R-',''),'ACC-JV-A-',''),'ACC-JVP-','') AS doc_no_field,
					je.voucher_type AS doc_type,
					je.user_remark AS reference,
					CASE
						WHEN je.user_remark LIKE '%%SA#%%'      THEN je.pay_to_recd_from
						WHEN je.user_remark LIKE '%%COS%%'      THEN 'CLOSED TO COS'
						WHEN je.user_remark LIKE '%%VP-ALPHA%%' THEN 'ADJUSTMENT TO COS'
						WHEN je.user_remark LIKE '%%INV%%'      THEN 'CLOSED TO COS'
						WHEN je.user_remark LIKE '%%VP#%%'      THEN jea.party
						ELSE jea.party
					END AS payee_received_from,
					jea.user_remark AS particulars,
					jea.debit AS debit,
					jea.credit AS credit,
					(jea.debit - jea.credit) AS net_change,
					CASE WHEN je.docstatus = 2 THEN 'Cancelled' ELSE 'Posted' END AS status_label,
					je.creation AS creation, je.modified_by AS modified_by,
					je.modified AS modified, je.owner AS owner
				FROM `tabJournal Entry` je
				JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
				WHERE je.docstatus IN (1, 2)
				  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
				  AND je.company = %(company)s
				  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND jea.project IS NOT NULL
				  AND jea.account LIKE '1521%%'
				UNION ALL
				SELECT pii.project AS jo_number,
					pi.posting_date AS tran_date,
					pi.remarks AS doc_no_field,
					'Purchase Invoice' AS doc_type,
					CONCAT(COALESCE(pii.item_code,''),' ',COALESCE(pii.item_name,'')) AS reference,
					pi.supplier AS payee_received_from,
					COALESCE(pii.description, pii.item_name, '') AS particulars,
					pii.base_amount AS debit,
					0 AS credit,
					pii.base_amount AS net_change,
					CASE WHEN pi.docstatus = 2 THEN 'Cancelled' ELSE 'Posted' END AS status_label,
					pi.creation AS creation, pi.modified_by AS modified_by,
					pi.modified AS modified, pi.owner AS owner
				FROM `tabPurchase Invoice Item` pii
				JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
				WHERE pi.docstatus IN (1, 2)
				  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
					   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
				  AND pi.company = %(company)s
				  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND pii.expense_account LIKE '1521%%'
			) c ON c.jo_number = j.jo_number
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §6  JE/PI TOTAL per JO
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 6,
				   NULL, NULL, '', NULL,
				   NULL, 'TOTAL:',
				   jp.debit, jp.credit, jp.net_change, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			JOIN (
				SELECT jo_number, SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT jea.project AS jo_number, jea.debit, jea.credit, (jea.debit-jea.credit) AS net_change
					FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
					WHERE je.docstatus=1 AND je.company=%(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND jea.project IS NOT NULL
					  AND jea.account LIKE '1521%%'
					UNION ALL
					SELECT pii.project, pii.base_amount, 0, pii.base_amount
					FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
					WHERE pi.docstatus=1 AND pi.company=%(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) jpx GROUP BY jo_number
			) jp ON jp.jo_number = j.jo_number
			WHERE COALESCE(jp.debit,0)<>0 OR COALESCE(jp.credit,0)<>0 OR COALESCE(jp.net_change,0)<>0
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §7  GRAND TOTAL per JO
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 7,
				   NULL, NULL, '', NULL,
				   NULL, '<b>GRAND TOTAL:</b>',
				   COALESCE(s.debit,0) + COALESCE(jp.debit,0),
				   COALESCE(s.credit,0) + COALESCE(jp.credit,0),
				   COALESCE(s.net_change,0) + COALESCE(jp.net_change,0),
				   NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			LEFT JOIN (
				SELECT jo_number, SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 0
							 ELSE ROUND(sed.amount, 2) END AS debit,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 0
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 ELSE 0 END AS credit,
						CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
							 WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
							 ELSE ROUND(sed.amount, 2) END AS net_change
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
					WHERE se.docstatus=1 AND se.company=%(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project,se.project) IS NOT NULL
				) sx GROUP BY jo_number
			) s ON s.jo_number = j.jo_number
			LEFT JOIN (
				SELECT jo_number, SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT jea.project AS jo_number, jea.debit, jea.credit, (jea.debit-jea.credit) AS net_change
					FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
					WHERE je.docstatus=1 AND je.company=%(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					  AND jea.account LIKE '1521%%'
					UNION ALL
					SELECT pii.project, pii.base_amount, 0, pii.base_amount
					FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
					WHERE pi.docstatus=1 AND pi.company=%(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) jpx GROUP BY jo_number
			) jp ON jp.jo_number = j.jo_number
			WHERE COALESCE(s.debit,0)+COALESCE(jp.debit,0)<>0
			   OR COALESCE(s.credit,0)+COALESCE(jp.credit,0)<>0
			   OR COALESCE(s.net_change,0)+COALESCE(jp.net_change,0)<>0
			UNION ALL
			/* ══════════════════════════════════════════════════════
			   §8 & §9  BLANK SEPARATOR ROWS
			══════════════════════════════════════════════════════ */
			SELECT 1, j.jo_number, 8, NULL, NULL, '', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			UNION ALL
			SELECT 1, j.jo_number, 9, NULL, NULL, '', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT jo_number FROM (
					SELECT COALESCE(sed.project, se.project) AS jo_number
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
					WHERE se.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND se.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND se.docstatus = 2))
					  AND se.company = %(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project, se.project) IS NOT NULL
					UNION
					SELECT jea.project FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
					WHERE je.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND je.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND je.docstatus = 2))
					  AND je.company = %(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					UNION
					SELECT pii.project FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
					WHERE pi.docstatus IN (1, 2)
					  AND (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'All transactions'
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Posted Transactions'    AND pi.docstatus = 1)
						   OR (COALESCE(NULLIF(%(status)s, ''), 'All transactions') = 'Cancelled Transactions' AND pi.docstatus = 2))
					  AND pi.company = %(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) src WHERE jo_number IS NOT NULL
			) j
			/* ══════════════════════════════════════════════════════
			   REPORT-WIDE FOOTER
			══════════════════════════════════════════════════════ */
			UNION ALL
			SELECT 2, NULL, 1, NULL, NULL, '', NULL,
				   'INVENTORY ENTRY TO GL', 'MR/MRS TOTAL:',
				   net_change, NULL, NULL, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT SUM(CASE
					WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
					WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
					ELSE ROUND(sed.amount, 2) END) AS net_change
				FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
				WHERE se.docstatus=1 AND se.company=%(company)s
				  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND COALESCE(sed.project,se.project) IS NOT NULL
				  AND CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 'MR'
						   WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 'MRS'
						   ELSE 'OTHER' END IN ('MR','MRS')
			) mmt WHERE COALESCE(net_change,0)<>0
			UNION ALL
			SELECT 2, NULL, 3, NULL, NULL, '', NULL,
				   '<b>INVENTORY ENTRY TO GL</b>', '<b>OVER ALL TOTAL:</b>',
				   mmt.net_change, NULL, glt.net_change, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT SUM(CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
								WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
								ELSE ROUND(sed.amount, 2) END) AS net_change
				FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
				WHERE se.docstatus=1 AND se.company=%(company)s
				  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				  AND COALESCE(sed.project,se.project) IS NOT NULL
				  AND CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 'MR'
						   WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 'MRS'
						   ELSE 'OTHER' END IN ('MR','MRS')
			) mmt
			CROSS JOIN (
				SELECT SUM(net_change) AS net_change
				FROM (
					SELECT CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
								WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
								ELSE ROUND(sed.amount, 2) END AS net_change
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
					WHERE se.docstatus=1 AND se.company=%(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project,se.project) IS NOT NULL
				) gx
			) glt
			WHERE COALESCE(mmt.net_change,0)<>0 OR COALESCE(glt.net_change,0)<>0
			UNION ALL
			SELECT 2, NULL, 4, NULL, NULL, '', NULL,
				   NULL, '<b>TOTAL:</b>',
				   debit, credit, net_change, NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT jea.debit, jea.credit, (jea.debit-jea.credit) AS net_change
					FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
					WHERE je.docstatus=1 AND je.company=%(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					  AND jea.account LIKE '1521%%'
					UNION ALL
					SELECT pii.base_amount, 0, pii.base_amount
					FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
					WHERE pi.docstatus=1 AND pi.company=%(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) jpx
			) jpt WHERE COALESCE(debit,0)<>0 OR COALESCE(credit,0)<>0 OR COALESCE(net_change,0)<>0
			UNION ALL
			SELECT 2, NULL, 5, NULL, NULL, '', NULL,
				   NULL, '<b>GRAND TOTAL:</b>',
				   glt.debit + jpt.debit,
				   glt.credit + jpt.credit,
				   glt.net_change + jpt.net_change,
				   NULL, NULL, NULL, NULL, NULL
			FROM (
				SELECT SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
								WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN 0
								ELSE ROUND(sed.amount, 2) END AS debit,
						   CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN 0
								WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
								ELSE 0 END AS credit,
						   CASE WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') LIKE 'Stores%%' THEN ROUND(sed.amount, 2)
								WHEN se.stock_entry_type='Material Transfer' AND COALESCE(sed.s_warehouse,'') NOT LIKE 'Stores%%' THEN -ROUND(sed.amount, 2)
								ELSE ROUND(sed.amount, 2) END AS net_change
					FROM `tabStock Entry` se JOIN `tabStock Entry Detail` sed ON sed.parent=se.name
					WHERE se.docstatus=1 AND se.company=%(company)s
					  AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
					  AND COALESCE(sed.project,se.project) IS NOT NULL
				) gx
			) glt
			CROSS JOIN (
				SELECT SUM(debit) AS debit, SUM(credit) AS credit, SUM(net_change) AS net_change
				FROM (
					SELECT jea.debit, jea.credit, (jea.debit-jea.credit) AS net_change
					FROM `tabJournal Entry` je JOIN `tabJournal Entry Account` jea ON jea.parent=je.name
					WHERE je.docstatus=1 AND je.company=%(company)s
					  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s AND jea.project IS NOT NULL
					  AND jea.account LIKE '1521%%'
					UNION ALL
					SELECT pii.base_amount, 0, pii.base_amount
					FROM `tabPurchase Invoice Item` pii JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
					WHERE pi.docstatus=1 AND pi.company=%(company)s
					  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s AND pii.expense_account LIKE '1521%%'
				) jpx
			) jpt
			WHERE COALESCE(glt.debit,0)+COALESCE(jpt.debit,0)<>0
			   OR COALESCE(glt.credit,0)+COALESCE(jpt.credit,0)<>0
			   OR COALESCE(glt.net_change,0)+COALESCE(jpt.net_change,0)<>0
		) r
		ORDER BY
			r.block_order,
			r.jo_number,
			r.section_order,
			r.tran_date,
			r.doc_no_field
	"""

	return frappe.db.sql(query, filters, as_dict=True)