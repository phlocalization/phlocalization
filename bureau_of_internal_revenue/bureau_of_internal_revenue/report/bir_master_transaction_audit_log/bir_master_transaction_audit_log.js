// Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
// For license information, please see license.txt

frappe.query_reports["BIR Master Transaction Audit Log"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			mandatory: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			mandatory: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			mandatory: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "Select",
			options: ["All Accounts", "Cost of Sales Accounts"].join("\n"),
			default: "All Accounts",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["All Transactions", "Posted Transactions", "Cancelled Transactions"].join("\n"),
			default: "Posted Transactions",
		},
	],
};