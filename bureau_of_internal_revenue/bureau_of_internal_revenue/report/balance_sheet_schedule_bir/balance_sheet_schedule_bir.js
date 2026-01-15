// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// Copyright (c) 2026, Ambibuzz Technologies LLP and Contributors
// License: GNU General Public License v3. See license.txt


frappe.query_reports["Balance Sheet Schedule BIR"] = $.extend(
	{},
	erpnext.financial_statements,
	{
		filters: erpnext.financial_statements.filters.filter(f =>
			!["cost_center", "project"].includes(f.fieldname)
		),
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
erpnext.utils.add_dimensions("Balance Sheet Schedule BIR", 10);

frappe.query_reports["Balance Sheet Schedule BIR"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Balance Sheet Schedule BIR"]["filters"].push({
	fieldname: "include_default_book_entries",
	label: __("Include Default FB Entries"),
	fieldtype: "Check",
	default: 1,
});
