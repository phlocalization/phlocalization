// Copyright (c) 2025, Ambibuzz Technologies LLP and contributors
// For license information, please see license.txt

frappe.query_reports["Balance Sheet BIR"] = $.extend(
	{},
	erpnext.financial_statements,
	{
		formatter(value, row, column, data, df) {
			const formatted = erpnext.financial_statements.formatter
				? erpnext.financial_statements.formatter(
						value,
						row,
						column,
						data,
						df
				  )
				: value;

			if (data && data.indent === 0 && typeof value === "number") {
				return "";
			}

			return formatted;
		},
	}
);

erpnext.utils.add_dimensions("Balance Sheet BIR", 10);

frappe.query_reports["Balance Sheet BIR"]["filters"].push({
	fieldname: "selected_view",
	label: __("Select View"),
	fieldtype: "Select",
	options: [
		{ value: "Report", label: __("Report View") },
		{ value: "Growth", label: __("Growth View") },
	],
	default: "Report",
	reqd: 1,
});

frappe.query_reports["Balance Sheet BIR"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Balance Sheet BIR"]["filters"].push({
	fieldname: "include_default_book_entries",
	label: __("Include Default FB Entries"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Balance Sheet BIR"]["filters"].push({
	fieldname: "level",
	label: __("Show Levels Upto"),
	fieldtype: "Select",
	options: ["1", "2", "3", "4", "All"],
	default: "All"
});