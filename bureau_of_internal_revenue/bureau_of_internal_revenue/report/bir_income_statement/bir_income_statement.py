# Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, get_last_day, add_years


MONTHS = [
	"january", "february", "march", "april", "may", "june",
	"july", "august", "september", "october", "november", "december",
]

MONTH_LABELS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

IS_SUMMARY_CONFIG = [
	{"type": "account",     "account_number": "4100", "bold": False},
	{"type": "account",     "account_number": "4200", "bold": False},
	{"type": "calculation", "label": "NET SALES",             "rows": [1, 2],    "bold": True},
	{"type": "account",     "account_number": "5001",         "bold": False},
	{"type": "calculation", "label": "GROSS PROFIT",          "rows": [3, 4], "bold": True},
	{"type": "account",     "account_number": "5100",         "bold": False},
	{"type": "calculation", "label": "NET OPERATING INCOME (LOSS)",  "rows": [5, 6],    "bold": True},
	{"type": "net_account", "account_numbers": ["6000", "5200"],
	 "label": "Other Income (Expenses), NET",                        "bold": False},
	{"type": "calculation", "label": "NET INCOME BEFORE TAX",     "rows": [7, 8],    "bold": True},
	{"type": "account",     "account_number": "5300",         "bold": False},
	{"type": "calculation", "label": "NET INCOME",            "rows": [9, 10],   "bold": True},
]

# TODO: In future, remove the Account Numbering
IS_WITH_COS_CONFIG = [
	{"type": "account_children", "account_number": "4100", "section_key": "gross_sales"},
	{"type": "account_children", "account_number": "4300", "section_key": "sales_discount"},
	{"type": "account_children", "account_number": "4200", "section_key": "sales_adj"},
	{"type": "calculation",      "label": "NET SALES",                                      "section_refs": ["gross_sales", "sales_discount", "sales_adj"],     "bold": True},
	{"type": "account_children", "account_number": "5001", "section_key": "cogs"},
	{"type": "calculation",      "label": "GROSS PROFIT",                                   "section_refs": ["net_sales", "cogs"],     "bold": True},
	{"type": "account_children", "account_number": "5100", "section_key": "opex"},
	{"type": "calculation",      "label": "NET OPERATING INCOME (LOSS)",      "section_refs": ["gross_profit", "opex"],        "bold": True},
	{"type": "account_children", "account_number": "6000", "section_key": "other_income"},
	{"type": "calculation",      "label": "NET PROFIT BEFORE OTHER EXPENSES",               "section_refs": ["net_op_income", "other_income"],       "bold": True},
	{"type": "account_children", "account_number": "5200", "section_key": "other_exp"},
	{"type": "calculation",      "label": "NET PROFIT BEFORE PROVISION FOR INCOME TAX",     "section_refs": ["net_before_other_exp", "other_exp"],      "bold": True},
	{"type": "account",          "account_number": "5300","section_key": "tax", "bold": False},
	{"type": "calculation",      "label": "NET PROFIT / (LOSS)",                            "section_refs": ["net_before_tax", "tax"],      "bold": True},
]

IS_WITH_COS_CALC_KEYS = [
	"net_sales",
	"gross_profit",
	"net_op_income",
	"net_before_other_exp",
	"net_before_tax",
	"net_profit",
]


def execute(filters=None):
	"""Entry point for the Frappe report framework.
	Validates the provided filters, then builds and returns the column
	definitions and row data for the selected report type.
	"""
	validate_filters(filters)
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def validate_filters(filters):
	"""Ensure all required filter fields are present and valid.
	Throws a user-facing error if company or fiscal year is missing,
	and defaults report_type to 'IS Summary' when not supplied.
	"""
	if not filters.get("company"):
		frappe.throw(_("Please select a Company"))
	if not filters.get("fiscal_year"):
		frappe.throw(_("Please select a Fiscal Year"))
	if not filters.get("report_type"):
		filters["report_type"] = "IS Summary"


def get_columns(filters):
	"""Build the list of column definitions for the report grid.
	Derives the current and previous fiscal year labels from the selected
	fiscal year, then appends one column per calendar month plus a YTD column.
	"""
	fy = frappe.get_doc("Fiscal Year", filters["fiscal_year"])
	current_year = getdate(fy.year_start_date).year
	prev_year = current_year - 1

	columns = [
		{"fieldname": "account", "label": _("Particulars"),              "fieldtype": "Data",     "width": 320},
		{"fieldname": "ytd_prev", "label": _("YTD {0}").format(prev_year), "fieldtype": "Currency", "precision": 2, "width": 150},
	]

	for label in MONTH_LABELS:
		columns.append({
			"fieldname": label.lower(),
			"label": _(label),
			"fieldtype": "Currency",
			"precision": 2,
			"width": 130,
		})

	columns.append({
		"fieldname": "ytd_current",
		"label": _("YTD {0}").format(current_year),
		"fieldtype": "Currency",
		"precision": 2,
		"width": 150,
	})

	return columns


def get_data(filters):
	"""Dispatch to the appropriate report builder based on report_type.
	Supports 'IS Summary', 'IS with COS', and 'Operating Exp per Dept';
	returns an empty list if the report type is unrecognised.
	"""
	report_type = filters.get("report_type", "IS Summary")

	if report_type == "IS Summary":
		return build_is_summary(filters)
	elif report_type == "IS with COS":
		return build_is_with_cos(filters)
	elif report_type == "Operating Exp per Dept":
		return build_op_exp_per_dept(filters)

	return []


def build_is_summary(filters):
	"""Construct the Income Statement Summary report rows.
	Iterates over IS_SUMMARY_CONFIG, creating GL account rows or derived
	calculation rows and accumulating them into the final data list.
	"""
	company = filters["company"]
	fy = frappe.get_doc("Fiscal Year", filters["fiscal_year"])
	year_start = getdate(fy.year_start_date)
	prev_start = add_years(year_start, -1)
	prev_end = add_years(getdate(fy.year_end_date), -1)
	extra_cond, extra_params = build_extra_conditions(filters)
	account_cache = {}
	data = []

	for cfg in IS_SUMMARY_CONFIG:
		if cfg["type"] == "account":
			row = build_gl_row(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache)
		elif cfg["type"] == "net_account":
			row = build_net_row(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache)
		else:
			row = build_calc_row(cfg, data)
		data.append(row)

	return data


def build_is_with_cos(filters):
	"""Construct the detailed Income Statement with Cost of Sales report rows.
	Processes IS_WITH_COS_CONFIG entries, expanding account groups into their
	child accounts and inserting subtotal and calculation rows between sections.
	"""
	company = filters["company"]
	fy = frappe.get_doc("Fiscal Year", filters["fiscal_year"])
	year_start = getdate(fy.year_start_date)
	prev_start = add_years(year_start, -1)
	prev_end = add_years(getdate(fy.year_end_date), -1)
	extra_cond, extra_params = build_extra_conditions(filters)
	account_cache = {}
	data = []
	section_totals = {}
	calc_key_index = 0

	for cfg in IS_WITH_COS_CONFIG:
		if cfg["type"] == "account_children":
			rows, total_row = build_children_rows(
				company, year_start, prev_start, prev_end,
				cfg, extra_cond, extra_params, account_cache, None
			)
			data.extend(rows)
			data.append(total_row)
			section_totals[cfg["section_key"]] = total_row

		elif cfg["type"] == "account":
			row = build_gl_row(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache)
			data.append(row)
			section_totals[cfg["section_key"]] = row

		elif cfg["type"] == "calculation":
			row = build_cos_calc_row(cfg, section_totals)
			data.append(row)
			section_totals[IS_WITH_COS_CALC_KEYS[calc_key_index]] = row
			calc_key_index += 1

	return data


def build_op_exp_per_dept(filters):
	"""Build the Operating Expenses per Department report rows.
	Groups leaf-level cost centers under their parent group, summing GL entries
	for the operating expense account tree into monthly and YTD columns.
	"""
	company = filters["company"]
	fy = frappe.get_doc("Fiscal Year", filters["fiscal_year"])
	year_start = getdate(fy.year_start_date)
	prev_start = add_years(year_start, -1)
	prev_end = add_years(getdate(fy.year_end_date), -1)
	extra_cond, extra_params = build_extra_conditions(filters)

	op_exp_account = frappe.db.get_value(
		"Account",
		{"account_number": "5100", "company": company, "is_group": 1},
		"name",
	)

	if not op_exp_account:
		return []

	op_lft, op_rgt = frappe.db.get_value("Account", op_exp_account, ["lft", "rgt"])

	expense_accounts = frappe.db.sql("""
		SELECT name, account_name, account_number, lft, rgt
		FROM `tabAccount`
		WHERE company = %(company)s
			AND is_group = 0
			AND lft >= %(lft)s AND rgt <= %(rgt)s
		ORDER BY account_number ASC
	""", {"company": company, "lft": op_lft, "rgt": op_rgt}, as_dict=True)

	cc_groups = frappe.db.sql("""
		SELECT name, cost_center_name, lft, rgt
		FROM `tabCost Center`
		WHERE company = %(company)s
			AND is_group = 1
			AND parent_cost_center IS NOT NULL
			AND parent_cost_center != ''
		ORDER BY lft ASC
	""", {"company": company}, as_dict=True)

	if not cc_groups:
		return []

	data = []
	grand_total_row = new_empty_row("GRAND TOTAL OPERATING EXPENSES", is_bold=True)

	for cc_group in cc_groups:
		child_ccs = frappe.db.sql("""
			SELECT name, cost_center_name
			FROM `tabCost Center`
			WHERE company = %(company)s
				AND is_group = 0
				AND lft > %(lft)s AND rgt < %(rgt)s
			ORDER BY lft ASC
		""", {"company": company, "lft": cc_group.lft, "rgt": cc_group.rgt}, as_dict=True)

		if not child_ccs:
			continue

		section_header = new_empty_row(cc_group.cost_center_name, is_bold=True)
		data.append(section_header)

		subtotal_row = new_empty_row("Total - {0}".format(cc_group.cost_center_name), is_bold=True)

		for cc in child_ccs:
			dept_header = new_empty_row(cc.cost_center_name, is_bold=True)
			data.append(dept_header)

			dept_total = new_empty_row("Total - {0}".format(cc.cost_center_name), is_bold=True)

			for acc in expense_accounts:
				acc_row = new_empty_row(acc.account_name, is_bold=False)

				for i, month_key in enumerate(MONTHS):
					m_start = get_first_day("{0}-{1:02d}-01".format(year_start.year, i + 1))
					m_end = get_last_day(m_start)
					acc_row[month_key] = get_balance_by_cc(
						company, acc.lft, acc.rgt, cc.name, m_start, m_end, extra_cond, extra_params
					)

				acc_row["ytd_current"] = flt(sum(flt(acc_row[m]) for m in MONTHS), 2)
				acc_row["ytd_prev"] = get_balance_by_cc(
					company, acc.lft, acc.rgt, cc.name, prev_start, prev_end, extra_cond, extra_params
				)

				has_data = any(flt(acc_row[m]) != 0 for m in MONTHS) or flt(acc_row["ytd_prev"]) != 0
				if has_data:
					data.append(acc_row)
					for field in MONTHS + ["ytd_prev", "ytd_current"]:
						dept_total[field] = flt(flt(dept_total.get(field, 0)) + flt(acc_row[field]), 2)

			data.append(dept_total)

			for field in MONTHS + ["ytd_prev", "ytd_current"]:
				subtotal_row[field] = flt(flt(subtotal_row.get(field, 0)) + flt(dept_total[field]), 2)

		data.append(subtotal_row)

		for field in MONTHS + ["ytd_prev", "ytd_current"]:
			grand_total_row[field] = flt(flt(grand_total_row.get(field, 0)) + flt(subtotal_row[field]), 2)

	data.append(grand_total_row)

	return data


def build_children_rows(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache, section_index):
	"""Expand a parent account into individual child account rows plus a total row.
	Queries direct non-group children of the resolved parent account, computes
	monthly and YTD balances for each, and accumulates them into a section total.
	"""
	acc_number = cfg["account_number"]
	account_name, parent_name = resolve_account(company, acc_number, account_cache)

	section_header_label = account_name or acc_number
	total_row = new_empty_row("TOTAL {0}".format(section_header_label.upper()), is_bold=True)
	rows = [new_empty_row(section_header_label, is_bold=True)]

	if not parent_name:
		return rows, total_row

	children = frappe.db.sql("""
		SELECT name, account_name, account_number
		FROM `tabAccount`
		WHERE parent_account = %(parent)s
			AND company = %(company)s
			AND is_group = 0
		ORDER BY account_number ASC
	""", {"parent": parent_name, "company": company}, as_dict=True)

	lft, rgt = frappe.db.get_value("Account", parent_name, ["lft", "rgt"])

	for child in children:
		child_lft, child_rgt = frappe.db.get_value("Account", child.name, ["lft", "rgt"])
		row = new_empty_row(child.account_name, is_bold=False)

		for i, month_key in enumerate(MONTHS):
			m_start = get_first_day("{0}-{1:02d}-01".format(year_start.year, i + 1))
			m_end = get_last_day(m_start)
			row[month_key] = get_balance(company, child_lft, child_rgt, m_start, m_end, extra_cond, extra_params)

		row["ytd_current"] = flt(sum(flt(row[m]) for m in MONTHS), 2)
		row["ytd_prev"] = get_balance(company, child_lft, child_rgt, prev_start, prev_end, extra_cond, extra_params)

		rows.append(row)

		for field in MONTHS + ["ytd_prev", "ytd_current"]:
			total_row[field] = flt(flt(total_row.get(field, 0)) + flt(row[field]), 2)

	return rows, total_row


def build_gl_row(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache):
	"""Build a single report row for a specific GL account group.
	Resolves the account by number, fetches monthly GL balances across the
	current fiscal year, and computes the current and prior-year YTD totals.
	"""
	acc_number = cfg["account_number"]
	account_name, parent_name = resolve_account(company, acc_number, account_cache)

	row = new_empty_row(account_name or acc_number, is_bold=cfg.get("bold", False))

	if not parent_name:
		return row

	lft, rgt = frappe.db.get_value("Account", parent_name, ["lft", "rgt"])

	for i, month_key in enumerate(MONTHS):
		m_start = get_first_day("{0}-{1:02d}-01".format(year_start.year, i + 1))
		m_end = get_last_day(m_start)
		row[month_key] = get_balance(company, lft, rgt, m_start, m_end, extra_cond, extra_params)

	row["ytd_current"] = flt(sum(flt(row[m]) for m in MONTHS), 2)
	row["ytd_prev"] = get_balance(company, lft, rgt, prev_start, prev_end, extra_cond, extra_params)

	return row


def build_net_row(company, year_start, prev_start, prev_end, cfg, extra_cond, extra_params, account_cache):
	row = new_empty_row(cfg["label"], is_bold=cfg.get("bold", False))

	for acc_number in cfg["account_numbers"]:
		account_name, parent_name = resolve_account(company, acc_number, account_cache)
		if not parent_name:
			continue

		lft, rgt = frappe.db.get_value("Account", parent_name, ["lft", "rgt"])

		for i, month_key in enumerate(MONTHS):
			m_start = get_first_day("{0}-{1:02d}-01".format(year_start.year, i + 1))
			m_end = get_last_day(m_start)
			row[month_key] = flt(flt(row[month_key]) + get_balance(
				company, lft, rgt, m_start, m_end, extra_cond, extra_params
			), 2)

		row["ytd_current"] = flt(sum(flt(row[m]) for m in MONTHS), 2)
		row["ytd_prev"] = flt(flt(row["ytd_prev"]) + get_balance(
			company, lft, rgt, prev_start, prev_end, extra_cond, extra_params
		), 2)

	return row


def build_cos_calc_row(cfg, section_totals):
	row = new_empty_row(cfg["label"], is_bold=cfg.get("bold", False))

	for field in MONTHS + ["ytd_prev", "ytd_current"]:
		total = 0
		for ref_key in cfg["section_refs"]:
			ref_row = section_totals.get(ref_key)
			if ref_row:
				total += flt(ref_row.get(field, 0))
		row[field] = flt(total, 2)

	return row


def build_calc_row(cfg, data):
	"""Derive a calculation row by summing previously built rows.
	Uses the 1-based row indices in cfg['rows'] to look up already-appended
	data rows and sums each monetary field to produce the calculated total.
	"""
	row = new_empty_row(cfg["label"], is_bold=cfg.get("bold", False))

	for field in MONTHS + ["ytd_prev", "ytd_current"]:
		total = 0
		for idx in cfg["rows"]:
			if 0 < idx <= len(data):
				total += flt(data[idx - 1].get(field, 0))
		row[field] = flt(total, 2)

	return row


def new_empty_row(label, is_bold=False):
	"""Create a blank row dict pre-populated with zero values for all fields.
	Initialises the account label and is_bold flag, then sets ytd_prev,
	ytd_current, and every monthly field to zero ready for accumulation.
	"""
	row = {
		"account": label,
		"is_bold": is_bold,
		"ytd_prev": 0,
		"ytd_current": 0,
	}
	for m in MONTHS:
		row[m] = 0
	return row


def resolve_account(company, account_number, cache):
	"""Look up an account by account_number within a company, with caching.
	Returns a tuple of (account_name, full_account_name) for the matched record,
	or (None, None) if no matching account is found in the database.
	"""
	if account_number in cache:
		return cache[account_number]

	result = frappe.db.get_value(
		"Account",
		{"account_number": account_number, "company": company},
		["account_name", "name"],
	)

	if result:
		cache[account_number] = (result[0], result[1])
		return result[0], result[1]

	cache[account_number] = (None, None)
	return None, None


def get_balance(company, lft, rgt, from_date, to_date, extra_cond, extra_params):
	"""Fetch the net credit-minus-debit balance for an account subtree over a date range.
	Selects all GL entries whose account falls within the lft/rgt nested-set bounds,
	applies any extra filter conditions, and returns the rounded sum or zero.
	"""
	params = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"lft": lft,
		"rgt": rgt,
	}
	params.update(extra_params)

	result = frappe.db.sql("""
		SELECT SUM(gle.credit - gle.debit)
		FROM `tabGL Entry` gle
		WHERE gle.company = %(company)s
			AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND gle.account IN (
				SELECT name FROM `tabAccount`
				WHERE lft >= %(lft)s AND rgt <= %(rgt)s AND company = %(company)s
			)
			AND gle.is_cancelled = 0
			{extra_cond}
	""".format(extra_cond=extra_cond), params)

	return flt(result[0][0], 2) if result and result[0][0] else 0


def get_balance_by_cc(company, lft, rgt, cost_center, from_date, to_date, extra_cond, extra_params):
	"""Fetch the net debit-minus-credit balance for a specific cost center over a date range.
	Filters GL entries to those belonging to accounts within the operating expense subtree
	and posted against the given cost center, then returns the rounded sum or zero.
	"""
	params = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"lft": lft,
		"rgt": rgt,
		"cost_center": cost_center,
	}
	params.update(extra_params)

	result = frappe.db.sql("""
		SELECT SUM(gle.debit - gle.credit)
		FROM `tabGL Entry` gle
		WHERE gle.company = %(company)s
			AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND gle.cost_center = %(cost_center)s
			AND gle.account IN (
				SELECT name FROM `tabAccount`
				WHERE lft >= %(lft)s AND rgt <= %(rgt)s AND company = %(company)s
			)
			AND gle.is_cancelled = 0
			{extra_cond}
	""".format(extra_cond=extra_cond), params)

	return flt(result[0][0], 2) if result and result[0][0] else 0


def build_extra_conditions(filters):
	"""Construct additional SQL WHERE clauses from optional filter fields.
	Checks for cost_center and project filters and appends parameterised
	conditions to the clause string, returning both the clause and its params dict.
	"""
	cond = ""
	params = {}
	if filters.get("cost_center"):
		cond += " AND gle.cost_center = %(cost_center)s"
		params["cost_center"] = filters["cost_center"]
	if filters.get("project"):
		cond += " AND gle.project = %(project)s"
		params["project"] = filters["project"]
	return cond, params