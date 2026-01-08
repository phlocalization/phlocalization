# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# Copyright (c) 2026, Ambibuzz Technologies LLP and Contributors
# MIT License. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

from bureau_of_internal_revenue.bureau_of_internal_revenue.report.balance_sheet_schedule_bir.balance_sheet_schedule_bir import (
	execute,
)


class TestBalanceSheetScheduleBIR(FrappeTestCase):
	"""
	Tests schedule-wise grouping and subtotal behavior
	for the Balance Sheet Schedule BIR report.
	"""

	@patch(
		"bureau_of_internal_revenue.bureau_of_internal_revenue.report.balance_sheet_schedule_bir.balance_sheet_schedule_bir.get_data"
	)
	@patch(
		"bureau_of_internal_revenue.bureau_of_internal_revenue.report.balance_sheet_schedule_bir.balance_sheet_schedule_bir.get_period_list"
	)
	@patch(
		"bureau_of_internal_revenue.bureau_of_internal_revenue.report.balance_sheet_schedule_bir.balance_sheet_schedule_bir.frappe.get_all"
	)
	def test_schedule_totals(self, mock_get_all, mock_get_period_list, mock_get_data):
		"""
		Ensure that schedule subtotal rows are generated
		and correctly sum values of child accounts.
		"""

		mock_get_period_list.return_value = [
			frappe._dict(
				key="2024",
				year_start_date="2024-01-01",
				year_end_date="2024-12-31",
			)
		]

		mock_get_all.return_value = [
			frappe._dict(name="Cash - _TC6", schedule="SCHED 1")
		]

		mock_get_data.return_value = [
			{
				"account_name": "Cash",
				"account": "Cash - _TC6",
				"indent": 2,
				"2024": 550,
				"total": 550,
			},
			{
				"account_name": "Cash Ledger",
				"account": "Cash - _TC6",
				"indent": 3,
				"2024": 550,
				"total": 550,
			},
			{},
		]

		filters = frappe._dict(
			company="_Test Company 6",
			from_fiscal_year="2024",
			to_fiscal_year="2024",
			periodicity="Yearly",
		)

		columns, data, *_ = execute(filters)

		self.assertEqual(columns[0]["fieldname"], "schedule")

		schedule_totals = {}
		current_schedule = None

		for row in data:
			if row.get("schedule"):
				current_schedule = row["schedule"]

			if row.get("account_name") == "Total" and current_schedule:
				schedule_totals[current_schedule] = row.get("total")

		self.assertEqual(schedule_totals.get("SCHED 1"), 550)
