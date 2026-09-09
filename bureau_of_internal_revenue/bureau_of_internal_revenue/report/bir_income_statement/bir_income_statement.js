// Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
// For license information, please see license.txt

frappe.query_reports["BIR Income Statement"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: frappe.defaults.get_user_default("fiscal_year"),
			reqd: 1,
		},
		{
			fieldname: "report_type",
			label: __("Report Type"),
			fieldtype: "Select",
			options: "IS Summary\nIS with COS\nOperating Exp per Dept",
			default: "IS Summary",
			reqd: 1,
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		if (column.fieldname === "account") {
			value = default_formatter(value, row, column, data);
			if (data.is_bold) {
				value = `<span style="font-weight:bold">${value}</span>`;
			}
			return value;
		}

		let num = data[column.fieldname];

		if (num === undefined || num === null || num === 0) {
			return data.is_bold ? `<span style="font-weight:bold">-</span>` : "-";
		}

		let abs_val = Math.abs(num);
		let display = format_currency(abs_val, null, 2);

		if (num < 0) {
			display = `<span style="color:red">(${display})</span>`;
		} else {
			display = `<span style="color:green">${display}</span>`;
		}

		if (data.is_bold) {
			display = `<span style="font-weight:bold">${display}</span>`;
		}

		return display;
	},
};