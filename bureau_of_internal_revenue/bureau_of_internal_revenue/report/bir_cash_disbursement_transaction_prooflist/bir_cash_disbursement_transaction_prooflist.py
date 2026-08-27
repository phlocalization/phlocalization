# Copyright (c) 2026, Ambibuzz Technologies LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import Case, CustomFunction, Order
from frappe.query_builder.functions import Coalesce, Concat, Max, Sum
from pypika.terms import ValueWrapper, NullValue

LPad = CustomFunction("LPAD", ["expr", "length", "pad"])
Replace = CustomFunction("REPLACE", ["expr", "find", "sub"])
Lower = CustomFunction("LOWER", ["expr"])
GroupConcat = CustomFunction("GROUP_CONCAT", ["expr"])


def execute(filters=None):
	"""
	Entry point returning report columns and data.
	Frappe calls this with the selected filters.
	"""
	return get_columns(), get_data(filters)


def get_columns():
	"""Return the report column definitions."""
	return [
		{"fieldname": "doc_type", "label": "Doc Type", "fieldtype": "Data", "width": 120},
		{"fieldname": "doc_no_html", "label": "Doc No", "fieldtype": "HTML", "width": 140},
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
		{"fieldname": "applied", "label": "Applied", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	"""
	Build and run the disbursement listing query.
	Unions detail, subtotal, spacer and grand-total rows, ordered by sort key.
	"""
	filters = filters or frappe._dict()
	company = filters.get("company")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	status = filters.get("status") or "Posted Only"

	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")
	ped = frappe.qb.DocType("Payment Entry Deduction")

	def pe_field(field):
		"""Scalar Payment Entry field for the current gle row."""
		pe = frappe.qb.DocType("Payment Entry")
		return frappe.qb.from_(pe).select(pe[field]).where(pe.name == gle.voucher_no)

	def je_field(field):
		"""Scalar Journal Entry field for the current gle row."""
		je = frappe.qb.DocType("Journal Entry")
		return frappe.qb.from_(je).select(je[field]).where(je.name == gle.voucher_no)

	def si_field(field):
		"""Scalar Sales Invoice field for the current gle row."""
		si = frappe.qb.DocType("Sales Invoice")
		return frappe.qb.from_(si).select(si[field]).where(si.name == gle.voucher_no)

	def per_alloc_for_ref():
		"""Allocated amount for the reference matching against_voucher."""
		per = frappe.qb.DocType("Payment Entry Reference")
		return (
			frappe.qb.from_(per)
			.select(per.allocated_amount)
			.where((per.parent == gle.voucher_no) & (per.reference_name == gle.against_voucher))
			.limit(1)
		)

	def pe_remarks():
		"""Parent Payment Entry remarks for the current gle row."""
		return pe_field("remarks")

	def base_conditions(q):
		"""
		Apply company, date, voucher and status filters to a block.
		Status is constant per run, so the cancelled flag is resolved here.
		"""
		pe = frappe.qb.DocType("Payment Entry")
		pay_names = frappe.qb.from_(pe).select(pe.name).where(pe.payment_type == "Pay")
		q = q.where(
			(gle.company == company)
			& (gle.posting_date[from_date:to_date])
			& (gle.voucher_type == "Payment Entry")
			& (gle.voucher_no.isin(pay_names))
		)
		if status == "Cancelled Only":
			q = q.where(gle.is_cancelled == 1)
		elif status == "Posted Only":
			q = q.where(gle.is_cancelled == 0)
		return q

	pe2 = frappe.qb.DocType("Payment Entry").as_("pe2")
	a2 = frappe.qb.DocType("Account").as_("a2")
	sii = frappe.qb.DocType("Sales Invoice Item")
	jea = frappe.qb.DocType("Journal Entry Account")
	p2 = frappe.qb.DocType("Payment Entry Reference").as_("p2")
	per = frappe.qb.DocType("Payment Entry Reference")

	is_bank = (
		acc.account_number.like("1203%")
		| acc.account_number.like("1205%")
		| acc.account_number.like("1214%")
	)

	transaction_date = (
		Case()
		.when(gle.voucher_type == "Journal Entry", je_field("cheque_date"))
		.when(gle.voucher_type == "Sales Invoice", si_field("posting_date"))
		.else_(gle.posting_date)
	)

	doc_type = (
		Case()
		.when(
			gle.voucher_type == "Payment Entry",
			frappe.qb.from_(pe2)
			.select(Concat(gle.voucher_type, " - ", pe2.payment_type))
			.where(pe2.name == gle.voucher_no),
		)
		.else_(gle.voucher_type)
	)

	doc_no_html = Concat(
		'<a href="/app/',
		Lower(Replace(gle.voucher_type, " ", "-")),
		"/", gle.voucher_no, '">', gle.voucher_no, "</a>",
	)

	bank_account = (
		frappe.qb.from_(pe2)
		.join(a2).on(a2.name == pe2.paid_from)
		.select(Concat(a2.account_number, " - ", a2.account_name))
		.where(pe2.name == gle.voucher_no)
	)

	reference_html = (
		Case()
		.when(gle.voucher_type == "Sales Invoice", Coalesce(si_field("remarks"), ""))
		.when(gle.voucher_type == "Journal Entry", Coalesce(je_field("cheque_no"), ""))
		.when(gle.voucher_type == "Payment Entry", Coalesce(pe_field("reference_no"), ""))
		.else_(Coalesce(gle.against_voucher, ""))
	)

	account = Concat(acc.account_number, " - ", acc.account_name)

	description = (
		Case()
		.when(is_bank, Coalesce(pe_field("reference_no"), ""))
		.when(acc.account_number.like("1301%"), Coalesce(pe_remarks(), ""))
		.when(acc.account_number.like("1604%"), Coalesce(ped.description, ""))
		.when(
			gle.voucher_type == "Sales Invoice",
			frappe.qb.from_(sii).select(GroupConcat(sii.description)).where(sii.parent == gle.voucher_no),
		)
		.when(
			gle.voucher_type == "Journal Entry",
			frappe.qb.from_(jea)
			.select(Coalesce(jea.user_remark, ""))
			.where(
				(jea.parent == gle.voucher_no)
				& (jea.account == gle.account)
				& (Coalesce(jea.debit, 0) == Coalesce(gle.debit, 0))
				& (Coalesce(jea.credit, 0) == Coalesce(gle.credit, 0))
			)
			.limit(1),
		)
		.else_(Coalesce(gle.remarks, ""))
	)

	_ri_pe = frappe.qb.DocType("Payment Entry")
	ri_cancelled = (
		frappe.qb.from_(_ri_pe)
		.select(Replace(Replace(_ri_pe.remarks, ",", ""), ".00", ""))
		.where(_ri_pe.name == gle.voucher_no)
	)
	ri_normal = (
		frappe.qb.from_(_ri_pe)
		.select(_ri_pe.remarks)
		.where(_ri_pe.name == gle.voucher_no)
	)
	if status == "Cancelled Only":
		reference_invoice = ri_cancelled
	elif status == "All":
		reference_invoice = Case().when(gle.is_cancelled == 1, ri_cancelled).else_(ri_normal)
	else:
		reference_invoice = ri_normal

	reference_date = (
		Case()
		.when(gle.voucher_type == "Journal Entry", je_field("cheque_date"))
		.when(gle.voucher_type == "Payment Entry", pe_field("reference_date"))
		.when(gle.voucher_type == "Sales Invoice", si_field("posting_date"))
		.else_(gle.posting_date)
	)

	remarks_match = (
		(Coalesce(pe_remarks(), "") != "")
		& ped.description.isnotnull()
		& ped.description.like(Concat("%", pe_remarks(), "%"))
	)

	def p2_pick(field):
		"""Pick a p2 field by reference match or remarks-in-description."""
		return (
			frappe.qb.from_(p2)
			.select(p2[field])
			.where((p2.parent == gle.voucher_no) & ((p2.reference_name == gle.against_voucher) | remarks_match))
			.limit(1)
		)

	amount = (
		Case()
		.when(acc.account_number.like("1604%"), p2_pick("allocated_amount"))
		.else_(per_alloc_for_ref())
	)

	per_sum_all = (
		frappe.qb.from_(per)
		.select(Coalesce(Sum(per.allocated_amount), 0))
		.where(per.parent == gle.voucher_no)
	)

	applied = (
		Case()
		.when(acc.account_number.like("1301%"), per_alloc_for_ref())
		.when(acc.account_number.like("1203%") | acc.account_number.like("1205%"), per_sum_all)
		.when(acc.account_number.like("1604%"), Coalesce(ped.amount, 0) * -1)
		.else_(Coalesce(gle.debit, 0) - Coalesce(gle.credit, 0))
	)

	per_idx_for_ref = (
		frappe.qb.from_(per)
		.select(per.idx)
		.where((per.parent == gle.voucher_no) & (per.reference_name == gle.against_voucher))
		.limit(1)
	)
	idx_pick = Case().when(acc.account_number.like("1604%"), p2_pick("idx")).else_(per_idx_for_ref)
	group_code = (
		Case()
		.when(acc.account_number.like("1301%"), "01")
		.when(acc.account_number.like("1604%"), "02")
		.else_("99")
	)
	sort_order = Concat(
		gle.posting_date, "-", gle.voucher_no, "-1-",
		LPad(Coalesce(idx_pick, 99999), 5, "0"),
		"-", group_code, "-", LPad(gle.idx, 5, "0"),
	)

	detail = (
		frappe.qb.from_(gle)
		.join(acc).on(acc.name == gle.account)
		.left_join(ped).on((ped.parent == gle.voucher_no) & (ped.account == gle.account))
		.select(
			doc_type.as_("doc_type"),
			doc_no_html.as_("doc_no_html"),
			transaction_date.as_("transaction_date"),
			gle.party.as_("Vendor_name"),
			bank_account.as_("bank_account"),
			pe_field("paid_amount").as_("paid_amount"),
			reference_html.as_("reference_html"),
			reference_invoice.as_("reference_invoice"),
			reference_date.as_("reference_date"),
			account.as_("account"),
			Coalesce(gle.cost_center, "").as_("cost_center"),
			description.as_("description"),
			amount.as_("amount"),
			applied.as_("applied"),
			sort_order.as_("sort_order"),
		)
		.where(~acc.account_number.like("1203%") & ~acc.account_number.like("1205%"))
	)
	detail = base_conditions(detail)

	# ---- SUBTOTAL ----
	# Use paid_amount for the amount column, and SUM(debit-credit)
	# excluding bank accounts for applied (bank rows net to zero).
	sub_paid_max = Max(pe_field("paid_amount"))
	subtotal_amount = sub_paid_max
	subtotal_applied = Sum(Coalesce(gle.debit, 0) - Coalesce(gle.credit, 0))
	subtotal_sort = Concat(gle.posting_date, "-", gle.voucher_no, "-2-0-00000")

	subtotal = (
		frappe.qb.from_(gle)
		.join(acc).on(acc.name == gle.account)
		.select(
			ValueWrapper("").as_("doc_type"),
			ValueWrapper("").as_("doc_no_html"),
			ValueWrapper("").as_("transaction_date"),
			ValueWrapper("").as_("Vendor_name"),
			ValueWrapper("").as_("bank_account"),
			NullValue().as_("paid_amount"),
			ValueWrapper("").as_("reference_html"),
			ValueWrapper("").as_("reference_invoice"),
			NullValue().as_("reference_date"),
			ValueWrapper("").as_("account"),
			ValueWrapper("").as_("cost_center"),
			ValueWrapper("<b>SUBTOTAL</b>").as_("description"),
			subtotal_amount.as_("amount"),
			subtotal_applied.as_("applied"),
			subtotal_sort.as_("sort_order"),
		)
		.where(~acc.account_number.like("1203%") & ~acc.account_number.like("1205%"))
		.groupby(gle.posting_date, gle.voucher_no)
	)
	subtotal = base_conditions(subtotal)

	spacer_sort = Concat(gle.posting_date, "-", gle.voucher_no, "-3-0-00000")
	spacer = (
		frappe.qb.from_(gle)
		.select(
			ValueWrapper("").as_("doc_type"),
			ValueWrapper("").as_("doc_no_html"),
			ValueWrapper("").as_("transaction_date"),
			ValueWrapper("").as_("Vendor_name"),
			ValueWrapper("").as_("bank_account"),
			NullValue().as_("paid_amount"),
			ValueWrapper("").as_("reference_html"),
			ValueWrapper("").as_("reference_invoice"),
			NullValue().as_("reference_date"),
			ValueWrapper("").as_("account"),
			ValueWrapper("").as_("cost_center"),
			ValueWrapper("").as_("description"),
			NullValue().as_("amount"),
			NullValue().as_("applied"),
			spacer_sort.as_("sort_order"),
		)
		.groupby(gle.posting_date, gle.voucher_no)
	)
	spacer = base_conditions(spacer)

	# ---- GRAND TOTAL ----
	# Same approach: paid_amount for amount, SUM(debit-credit) excluding bank for applied.
	gt_sub_amount = Max(pe_field("paid_amount"))
	gt_sub_applied = Sum(Coalesce(gle.debit, 0) - Coalesce(gle.credit, 0))

	gt_inner = (
		frappe.qb.from_(gle)
		.join(acc).on(acc.name == gle.account)
		.select(gle.voucher_no, gt_sub_amount.as_("sub_amount"), gt_sub_applied.as_("sub_applied"))
		.where(~acc.account_number.like("1203%") & ~acc.account_number.like("1205%"))
		.groupby(gle.voucher_no)
	)
	gt_inner = base_conditions(gt_inner).as_("_grand_total_sub")

	grand = frappe.qb.from_(gt_inner).select(
		ValueWrapper("").as_("doc_type"),
		ValueWrapper("").as_("doc_no_html"),
		ValueWrapper("").as_("transaction_date"),
		ValueWrapper("").as_("Vendor_name"),
		ValueWrapper("").as_("bank_account"),
		NullValue().as_("paid_amount"),
		ValueWrapper("").as_("reference_html"),
		ValueWrapper("").as_("reference_invoice"),
		NullValue().as_("reference_date"),
		ValueWrapper("").as_("account"),
		ValueWrapper("").as_("cost_center"),
		ValueWrapper("<b>GRAND TOTAL</b>").as_("description"),
		Sum(gt_inner.sub_amount).as_("amount"),
		Sum(gt_inner.sub_applied).as_("applied"),
		ValueWrapper("ZZZZ-GRAND-TOTAL").as_("sort_order"),
	)

	combined = detail * subtotal * spacer * grand
	combined = combined.orderby("sort_order", order=Order.asc)

	return combined.run(as_dict=True)