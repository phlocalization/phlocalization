# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# Copyright (c) 2026, Ambibuzz Technologies LLP and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.accounts.report.financial_statements import (
	get_columns,
	get_data,
	get_filtered_list_for_consolidated_report,
	get_period_list,
)


def execute(filters=None):
	"""
	Main entry point for the Balance Sheet report.
	Builds columns, data, summaries, and return payload.
	"""
	filters = frappe._dict(filters or {})

	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)

	filters.period_start_date = period_list[0]["year_start_date"]

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)

	asset = get_data(
		filters.company,
		"Asset",
		"Debit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)

	liability = get_data(
		filters.company,
		"Liability",
		"Credit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)

	equity = get_data(
		filters.company,
		"Equity",
		"Credit",
		period_list,
		only_current_fiscal_year=False,
		filters=filters,
		accumulated_values=filters.accumulated_values,
	)

	provisional_profit_loss, total_credit = get_provisional_profit_loss(
		asset, liability, equity, period_list, filters.company, currency
	)

	message, opening_balance = check_opening_balance(asset, liability, equity)

	account_schedules = {
		d.name: d.schedule
		for d in frappe.get_all(
			"Account",
			fields=["name", "schedule"],
			filters={"schedule": ["!=", ""]},
		)
	}

	data = []
	data.extend(asset or [])
	data.extend(liability or [])
	data.extend(equity or [])
	if opening_balance and round(opening_balance, 2) != 0:
		unclosed = {
			"account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"warn_if_negative": True,
			"currency": currency,
		}
		for period in period_list:
			unclosed[period.key] = opening_balance
			if provisional_profit_loss:
				provisional_profit_loss[period.key] = provisional_profit_loss[period.key] - opening_balance

		unclosed["total"] = opening_balance
		data.append(unclosed)

	if provisional_profit_loss:
		data.append(provisional_profit_loss)
	if total_credit:
		data.append(total_credit)

	columns = get_columns(
		filters.periodicity, period_list, filters.accumulated_values, company=filters.company
	)

	value_fields = {c["fieldname"] for c in columns if c.get("fieldtype") == "Currency"}
	value_fields.add("total")

	final_data = []
	current_schedule = None
	schedule_total = {}

	def flush_schedule_total():
		"""Append a Schedule subtotal row to final_data if a Schedule is active."""
		if not current_schedule:
			return
		row = {
			"account_name": _("Total"),
			"schedule": "",
			"indent": 1,
			"is_group": 1,
		}
		for k, v in schedule_total.items():
			row[k] = v
		final_data.append(row)

	for row in data:
		if row.get("is_group") and not row.get("parent_account"):
			continue
		
		account = row.get("account")
		schedule = account_schedules.get(account)
		is_group = row.get("is_group")

		if is_group and schedule:
			flush_schedule_total()

			final_data.append({
				"schedule": schedule,
				"account_name": row.get("account_name"),
				"indent": 0,
				"is_group": 1,
			})

			current_schedule = schedule
			schedule_total = {}
			continue

		if current_schedule and not is_group:
			row_copy = row.copy()
			row_copy["schedule"] = ""
			final_data.append(row_copy)

			for key in value_fields:
				if isinstance(row_copy.get(key), (int, float)):
					schedule_total[key] = schedule_total.get(key, 0) + row_copy[key]
			continue

		flush_schedule_total()
		current_schedule = None
		schedule_total = {}
		final_data.append(row)

	flush_schedule_total()

	columns.insert(
		0,
		{
			"label": _("Schedule"),
			"fieldname": "schedule",
			"fieldtype": "Data",
			"width": 100,
		},
	)

	chart = None

	report_summary, primitive_summary = get_report_summary(
		period_list, asset, liability, equity, provisional_profit_loss, currency, filters
	)

	return columns, final_data, message, chart, report_summary, primitive_summary


def get_provisional_profit_loss(
	asset, liability, equity, period_list, company, currency=None, consolidated=False
):
	"""
	Computes provisional profit or loss for the period.
	Also prepares a total credit row.
	"""
	provisional_profit_loss = {}
	total_row = {}
	if asset:
		total = total_row_total = 0
		currency = currency or frappe.get_cached_value("Company", company, "default_currency")
		total_row = {
			"account_name": "'" + _("Total (Credit)") + "'",
			"account": "'" + _("Total (Credit)") + "'",
			"warn_if_negative": True,
			"currency": currency,
		}
		has_value = False

		for period in period_list:
			key = period if consolidated else period.key
			total_assets = flt(asset[-2].get(key))
			effective_liability = 0.00

			if liability and liability[-1] == {}:
				effective_liability += flt(liability[-2].get(key))
			if equity and equity[-1] == {}:
				effective_liability += flt(equity[-2].get(key))

			provisional_profit_loss[key] = total_assets - effective_liability
			total_row[key] = provisional_profit_loss[key] + effective_liability

			if provisional_profit_loss[key]:
				has_value = True

			total += flt(provisional_profit_loss[key])
			provisional_profit_loss["total"] = total

			total_row_total += flt(total_row[key])
			total_row["total"] = total_row_total

		if has_value:
			provisional_profit_loss.update(
				{
					"account_name": "'" + _("Provisional Profit / Loss (Credit)") + "'",
					"account": "'" + _("Provisional Profit / Loss (Credit)") + "'",
					"warn_if_negative": True,
					"currency": currency,
				}
			)

	return provisional_profit_loss, total_row


def check_opening_balance(asset, liability, equity):
	"""
	Check if previous year balance sheet closed
	"""
	opening_balance = 0
	float_precision = cint(frappe.db.get_default("float_precision")) or 2
	if asset:
		opening_balance = flt(asset[-1].get("opening_balance", 0), float_precision)
	if liability:
		opening_balance -= flt(liability[-1].get("opening_balance", 0), float_precision)
	if equity:
		opening_balance -= flt(equity[-1].get("opening_balance", 0), float_precision)

	opening_balance = flt(opening_balance, float_precision)
	if opening_balance:
		return _("Previous Financial Year is not closed"), opening_balance
	return None, None


def get_report_summary(
	period_list,
	asset,
	liability,
	equity,
	provisional_profit_loss,
	currency,
	filters,
	consolidated=False,
):
	"""
	Builds high-level financial totals for report summary.
	Supports accumulated and consolidated views.
	"""
	net_asset, net_liability, net_equity, net_provisional_profit_loss = 0.0, 0.0, 0.0, 0.0

	if filters.get("accumulated_values"):
		period_list = [period_list[-1]]

	# from consolidated financial statement
	if filters.get("accumulated_in_group_company"):
		period_list = get_filtered_list_for_consolidated_report(filters, period_list)

	for period in period_list:
		key = period if consolidated else period.key
		if asset:
			net_asset += asset[-2].get(key)
		if liability and liability[-1] == {}:
			net_liability += liability[-2].get(key)
		if equity and equity[-1] == {}:
			net_equity += equity[-2].get(key)
		if provisional_profit_loss:
			net_provisional_profit_loss += provisional_profit_loss.get(key)

	return [
		{"value": net_asset, "label": _("Total Asset"), "datatype": "Currency", "currency": currency},
		{
			"value": net_liability,
			"label": _("Total Liability"),
			"datatype": "Currency",
			"currency": currency,
		},
		{"value": net_equity, "label": _("Total Equity"), "datatype": "Currency", "currency": currency},
		{
			"value": net_provisional_profit_loss,
			"label": _("Provisional Profit / Loss (Credit)"),
			"indicator": "Green" if net_provisional_profit_loss > 0 else "Red",
			"datatype": "Currency",
			"currency": currency,
		},
	], (net_asset - net_liability + net_equity)
