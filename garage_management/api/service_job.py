# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, nowdate


def _get_job(name):
	job = frappe.get_doc("Service Job", name)
	if not job.billing_items:
		frappe.throw(_("Add Billing Items on the Service Job before creating commercial documents"))
	return job


def _settings():
	return frappe.get_cached_doc("Service Job Settings")


def _item_row_from_billing(row):
	return {
		"item_code": row.item_code,
		"item_name": row.item_name,
		"description": row.description,
		"qty": row.qty,
		"rate": row.rate,
		"uom": frappe.db.get_value("Item", row.item_code, "stock_uom") or "Nos",
		"conversion_factor": 1.0,
		"warehouse": row.warehouse,
	}


@frappe.whitelist()
def create_quotation(service_job):
	job = _get_job(service_job)
	if job.quotation and frappe.db.exists("Quotation", job.quotation):
		frappe.throw(_("Quotation {0} already linked").format(job.quotation))

	settings = _settings()
	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = job.customer
	quotation.company = job.company
	quotation.transaction_date = nowdate()
	quotation.order_type = "Sales"
	if settings.default_price_list:
		quotation.selling_price_list = settings.default_price_list

	tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": job.company, "is_default": 1}
	)
	if tax_template:
		quotation.taxes_and_charges = tax_template

	if hasattr(quotation, "service_job"):
		quotation.service_job = job.name

	for row in job.billing_items or []:
		quotation.append("items", _item_row_from_billing(row))

	if not job.billing_items:
		quotation.flags.ignore_mandatory = True
		quotation.net_total = 0.0
		quotation.total = 0.0
		quotation.grand_total = 0.0
		quotation.base_grand_total = 0.0
		quotation.rounded_total = 0.0

	quotation.run_method("set_missing_values")
	quotation.set_taxes()
	quotation.run_method("calculate_taxes_and_totals")

	if not job.billing_items:
		if quotation.grand_total is None:
			quotation.grand_total = 0.0
		if quotation.base_grand_total is None:
			quotation.base_grand_total = 0.0
		if quotation.net_total is None:
			quotation.net_total = 0.0
		if quotation.total is None:
			quotation.total = 0.0
		if quotation.rounded_total is None:
			quotation.rounded_total = 0.0

	quotation.insert(ignore_permissions=True)

	job.db_set(
		{
			"quotation": quotation.name,
			"status": "Quoted",
		},
		update_modified=True,
	)

	frappe.msgprint(_("Quotation {0} created").format(quotation.name), indicator="green", alert=True)
	return quotation.name


@frappe.whitelist()
def mark_customer_approved(service_job):
	job = frappe.get_doc("Service Job", service_job)
	if job.quotation and frappe.db.exists("Quotation", job.quotation):
		qdoc = frappe.get_doc("Quotation", job.quotation)
		if qdoc.docstatus == 0:
			try:
				qdoc.flags.ignore_permissions = True
				qdoc.submit()
			except Exception:
				pass

	job.db_set({"status": "In Progress"}, update_modified=True)
	frappe.msgprint(_("Customer approved — job is In Progress"), indicator="green", alert=True)
	return job.name


@frappe.whitelist()
def create_sales_order(service_job):
	job = _get_job(service_job)
	if job.sales_order and frappe.db.exists("Sales Order", job.sales_order):
		frappe.throw(_("Sales Order {0} already linked").format(job.sales_order))

	if not job.quotation:
		frappe.throw(_("Create a Quotation first"))

	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	so = make_sales_order(job.quotation)
	if hasattr(so, "service_job"):
		so.service_job = job.name
	so.insert(ignore_permissions=True)

	job.db_set({"sales_order": so.name, "status": "In Progress"}, update_modified=True)
	frappe.msgprint(_("Sales Order {0} created").format(so.name), indicator="green", alert=True)
	return so.name


@frappe.whitelist()
def create_sales_invoice(service_job):
	job = _get_job(service_job)
	if job.sales_invoice and frappe.db.exists("Sales Invoice", job.sales_invoice):
		frappe.throw(_("Sales Invoice {0} already linked").format(job.sales_invoice))

	settings = _settings()
	si = None

	if job.quotation and frappe.db.exists("Quotation", job.quotation):
		qdoc = frappe.get_doc("Quotation", job.quotation)
		if qdoc.docstatus == 0:
			try:
				qdoc.flags.ignore_permissions = True
				qdoc.submit()
			except Exception:
				pass
		try:
			from erpnext.selling.doctype.quotation.quotation import make_sales_invoice

			si = make_sales_invoice(job.quotation)
		except Exception:
			si = None

		if not si:
			si = frappe.new_doc("Sales Invoice")
			si.customer = job.customer
			si.company = job.company
			si.posting_date = nowdate()
			if settings.default_price_list:
				si.selling_price_list = settings.default_price_list
			tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
				"Sales Taxes and Charges Template", {"company": job.company, "is_default": 1}
			)
			if tax_template:
				si.taxes_and_charges = tax_template
			for row in job.billing_items:
				si.append("items", _item_row_from_billing(row))
			si.run_method("set_missing_values")
			si.set_taxes()
			si.run_method("calculate_taxes_and_totals")
	elif job.sales_order and frappe.db.exists("Sales Order", job.sales_order):
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		si = make_sales_invoice(job.sales_order)
	else:
		if not job.billing_items:
			frappe.throw(_("Add items to Service Job or create Quotation first"))
		si = frappe.new_doc("Sales Invoice")
		si.customer = job.customer
		si.company = job.company
		si.posting_date = nowdate()
		if settings.default_price_list:
			si.selling_price_list = settings.default_price_list
		tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": job.company, "is_default": 1}
		)
		if tax_template:
			si.taxes_and_charges = tax_template
		for row in job.billing_items:
			si.append("items", _item_row_from_billing(row))
		si.run_method("set_missing_values")
		si.set_taxes()
		si.run_method("calculate_taxes_and_totals")

	# Inventory: deduct stock on invoice submit for stock items
	si.update_stock = 1
	default_wh = settings.default_warehouse
	for item in si.items:
		is_stock = cint_item_stock(item.item_code)
		if is_stock:
			if not item.warehouse:
				item.warehouse = default_wh
			if not item.warehouse:
				frappe.throw(
					_("Set Default Selling Warehouse in Service Job Settings (needed for stock item {0})").format(
						item.item_code
					)
				)
		else:
			item.warehouse = None

	if hasattr(si, "service_job"):
		si.service_job = job.name

	si.run_method("calculate_taxes_and_totals")
	si.insert(ignore_permissions=True)

	job.db_set({"sales_invoice": si.name, "status": "Invoiced"}, update_modified=True)
	frappe.msgprint(
		_("Sales Invoice {0} created with Update Stock enabled").format(si.name),
		indicator="green",
		alert=True,
	)
	return si.name


@frappe.whitelist()
def unlink_quotation(service_job):
	job = frappe.get_doc("Service Job", service_job)
	if not job.quotation:
		frappe.throw(_("No Quotation linked to Service Job {0}").format(service_job))

	old_quotation = job.quotation
	status = "Draft" if job.status in ("Quoted", "Awaiting Approval") else job.status
	job.db_set({"quotation": None, "status": status}, update_modified=True)

	if frappe.db.exists("Quotation", old_quotation):
		if frappe.db.has_column("Quotation", "service_job"):
			frappe.db.set_value("Quotation", old_quotation, "service_job", None, update_modified=False)
		if frappe.db.has_column("Quotation", "service_request"):
			frappe.db.set_value("Quotation", old_quotation, "service_request", None, update_modified=False)

	frappe.msgprint(_("Quotation {0} unlinked from Service Job").format(old_quotation), indicator="green", alert=True)
	return {"unlinked": old_quotation}


@frappe.whitelist()
def unlink_sales_order(service_job):
	job = frappe.get_doc("Service Job", service_job)
	if not job.sales_order:
		frappe.throw(_("No Sales Order linked to Service Job {0}").format(service_job))

	old_so = job.sales_order
	job.db_set({"sales_order": None}, update_modified=True)

	if frappe.db.exists("Sales Order", old_so):
		if frappe.db.has_column("Sales Order", "service_job"):
			frappe.db.set_value("Sales Order", old_so, "service_job", None, update_modified=False)
		if frappe.db.has_column("Sales Order", "service_request"):
			frappe.db.set_value("Sales Order", old_so, "service_request", None, update_modified=False)

	frappe.msgprint(_("Sales Order {0} unlinked from Service Job").format(old_so), indicator="green", alert=True)
	return {"unlinked": old_so}


@frappe.whitelist()
def unlink_sales_invoice(service_job):
	job = frappe.get_doc("Service Job", service_job)
	if not job.sales_invoice:
		frappe.throw(_("No Sales Invoice linked to Service Job {0}").format(service_job))

	old_si = job.sales_invoice
	status = "Completed" if job.status == "Invoiced" else job.status
	job.db_set({"sales_invoice": None, "status": status}, update_modified=True)

	if frappe.db.exists("Sales Invoice", old_si):
		if frappe.db.has_column("Sales Invoice", "service_job"):
			frappe.db.set_value("Sales Invoice", old_si, "service_job", None, update_modified=False)
		if frappe.db.has_column("Sales Invoice", "service_request"):
			frappe.db.set_value("Sales Invoice", old_si, "service_request", None, update_modified=False)

	frappe.msgprint(_("Sales Invoice {0} unlinked from Service Job").format(old_si), indicator="green", alert=True)
	return {"unlinked": old_si}


def cint_item_stock(item_code):
	return frappe.db.get_value("Item", item_code, "is_stock_item")


def on_sales_invoice_submit(doc, method=None):
	if getattr(doc, "service_job", None) and frappe.db.exists("Service Job", doc.service_job):
		frappe.db.set_value("Service Job", doc.service_job, {"sales_invoice": doc.name, "status": "Invoiced"})


def on_sales_invoice_cancel(doc, method=None):
	_clear_commercial_reference("Sales Invoice", doc.name, "sales_invoice")


def on_sales_invoice_trash(doc, method=None):
	_clear_commercial_reference("Sales Invoice", doc.name, "sales_invoice")


def on_sales_invoice_cancel_hook(doc, method=None):
	_clear_commercial_reference("Sales Invoice", doc.name, "sales_invoice")


def on_quotation_trash(doc, method=None):
	_clear_commercial_reference("Quotation", doc.name, "quotation")


def on_quotation_cancel(doc, method=None):
	_clear_commercial_reference("Quotation", doc.name, "quotation")


def on_sales_order_trash(doc, method=None):
	_clear_commercial_reference("Sales Order", doc.name, "sales_order")


def on_sales_order_cancel(doc, method=None):
	_clear_commercial_reference("Sales Order", doc.name, "sales_order")


def _clear_commercial_reference(doctype, docname, fieldname):
	"""Safely clear references before document deletion or on cancellation."""
	# Clear on Service Job
	if frappe.db.exists("DocType", "Service Job"):
		jobs = frappe.get_all("Service Job", filters={fieldname: docname}, pluck="name")
		for j in jobs:
			job_doc = frappe.get_doc("Service Job", j)
			status = job_doc.status
			if fieldname == "quotation" and status in ("Quoted", "Awaiting Approval"):
				status = "Draft"
			elif fieldname == "sales_invoice" and status == "Invoiced":
				status = "Completed"
			job_doc.db_set({fieldname: None, "status": status}, update_modified=False)

	# Clear on Service Request
	if frappe.db.exists("DocType", "Service Request"):
		requests = frappe.get_all("Service Request", filters={fieldname: docname}, pluck="name")
		for r in requests:
			req_doc = frappe.get_doc("Service Request", r)
			status = req_doc.status
			if fieldname == "quotation" and status in ("Quoted", "Awaiting Approval"):
				status = "Draft"
			elif fieldname == "sales_invoice" and status == "Invoiced":
				status = "Completed"
			req_doc.db_set({fieldname: None, "status": status}, update_modified=False)
