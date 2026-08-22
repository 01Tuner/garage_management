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
	if settings.default_taxes_and_charges:
		quotation.taxes_and_charges = settings.default_taxes_and_charges

	if hasattr(quotation, "service_job"):
		quotation.service_job = job.name

	for row in job.billing_items:
		quotation.append("items", _item_row_from_billing(row))

	if quotation.taxes_and_charges:
		quotation.set_taxes()

	quotation.insert(ignore_permissions=True)
	quotation.submit()

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
	updates = {"status": "In Progress"}

	if job.quotation and not job.sales_order:
		so_name = create_sales_order(service_job)
		updates["sales_order"] = so_name

	job.db_set(updates, update_modified=True)
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

	if job.sales_order:
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		si = make_sales_invoice(job.sales_order)
	elif job.quotation:
		# Cash path: build SI from job billing lines (quotation reference kept on job)
		si = frappe.new_doc("Sales Invoice")
		si.customer = job.customer
		si.company = job.company
		si.posting_date = nowdate()
		if settings.default_price_list:
			si.selling_price_list = settings.default_price_list
		if settings.default_taxes_and_charges:
			si.taxes_and_charges = settings.default_taxes_and_charges
		for row in job.billing_items:
			si.append("items", _item_row_from_billing(row))
		if si.taxes_and_charges:
			si.set_taxes()
	else:
		frappe.throw(_("Create Quotation or Sales Order first"))

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

	si.insert(ignore_permissions=True)

	job.db_set({"sales_invoice": si.name, "status": "Invoiced"}, update_modified=True)
	frappe.msgprint(
		_("Sales Invoice {0} created with Update Stock enabled").format(si.name),
		indicator="green",
		alert=True,
	)
	return si.name


def cint_item_stock(item_code):
	return frappe.db.get_value("Item", item_code, "is_stock_item")


def on_sales_invoice_submit(doc, method=None):
	if not getattr(doc, "service_job", None):
		return
	if frappe.db.exists("Service Job", doc.service_job):
		frappe.db.set_value("Service Job", doc.service_job, {"sales_invoice": doc.name, "status": "Invoiced"})


def on_sales_invoice_cancel(doc, method=None):
	if not getattr(doc, "service_job", None):
		return
	if frappe.db.exists("Service Job", doc.service_job):
		job = frappe.get_doc("Service Job", doc.service_job)
		status = "Completed" if job.status == "Invoiced" else job.status
		frappe.db.set_value("Service Job", doc.service_job, {"sales_invoice": None, "status": status})
