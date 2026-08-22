# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def _get_request(name):
	doc = frappe.get_doc("Service Request", name)
	if not doc.billing_items:
		frappe.throw(_("Add Billing Items on the Service Request before creating commercial documents"))
	return doc


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
def create_quotation(service_request):
	req = _get_request(service_request)
	if req.quotation and frappe.db.exists("Quotation", req.quotation):
		frappe.throw(_("Quotation {0} already linked").format(req.quotation))

	settings = _settings()
	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = req.customer
	quotation.company = req.company
	quotation.transaction_date = nowdate()
	quotation.order_type = "Sales"
	if settings.default_price_list:
		quotation.selling_price_list = settings.default_price_list
	if settings.default_taxes_and_charges:
		quotation.taxes_and_charges = settings.default_taxes_and_charges

	if hasattr(quotation, "service_request"):
		quotation.service_request = req.name

	for row in req.billing_items:
		quotation.append("items", _item_row_from_billing(row))

	if quotation.taxes_and_charges:
		quotation.set_taxes()

	quotation.insert(ignore_permissions=True)
	quotation.submit()

	req.db_set({"quotation": quotation.name, "status": "Quoted"}, update_modified=True)
	frappe.msgprint(_("Quotation {0} created").format(quotation.name), indicator="green", alert=True)
	return quotation.name


@frappe.whitelist()
def mark_customer_approved(service_request):
	req = frappe.get_doc("Service Request", service_request)
	updates = {"status": "In Progress"}

	if req.quotation and not req.sales_order:
		so_name = create_sales_order(service_request)
		updates["sales_order"] = so_name

	req.db_set(updates, update_modified=True)
	frappe.msgprint(_("Customer approved — request is In Progress"), indicator="green", alert=True)
	return req.name


@frappe.whitelist()
def create_sales_order(service_request):
	req = _get_request(service_request)
	if req.sales_order and frappe.db.exists("Sales Order", req.sales_order):
		frappe.throw(_("Sales Order {0} already linked").format(req.sales_order))

	if not req.quotation:
		frappe.throw(_("Create a Quotation first"))

	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	so = make_sales_order(req.quotation)
	if hasattr(so, "service_request"):
		so.service_request = req.name
	so.insert(ignore_permissions=True)

	req.db_set({"sales_order": so.name, "status": "In Progress"}, update_modified=True)
	frappe.msgprint(_("Sales Order {0} created").format(so.name), indicator="green", alert=True)
	return so.name


@frappe.whitelist()
def create_sales_invoice(service_request):
	req = _get_request(service_request)
	if req.sales_invoice and frappe.db.exists("Sales Invoice", req.sales_invoice):
		frappe.throw(_("Sales Invoice {0} already linked").format(req.sales_invoice))

	settings = _settings()
	si = None

	if req.sales_order:
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		si = make_sales_invoice(req.sales_order)
	elif req.quotation:
		si = frappe.new_doc("Sales Invoice")
		si.customer = req.customer
		si.company = req.company
		si.posting_date = nowdate()
		if settings.default_price_list:
			si.selling_price_list = settings.default_price_list
		if settings.default_taxes_and_charges:
			si.taxes_and_charges = settings.default_taxes_and_charges
		for row in req.billing_items:
			si.append("items", _item_row_from_billing(row))
		if si.taxes_and_charges:
			si.set_taxes()
	else:
		frappe.throw(_("Create Quotation or Sales Order first"))

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

	if hasattr(si, "service_request"):
		si.service_request = req.name

	si.insert(ignore_permissions=True)

	req.db_set({"sales_invoice": si.name, "status": "Invoiced"}, update_modified=True)
	frappe.msgprint(
		_("Sales Invoice {0} created with Update Stock enabled").format(si.name),
		indicator="green",
		alert=True,
	)
	return si.name


def cint_item_stock(item_code):
	return frappe.db.get_value("Item", item_code, "is_stock_item")


@frappe.whitelist()
def get_workshop_docs(service_request):
	return {
		"inspections": frappe.get_all(
			"Inspection",
			filters={"service_request": service_request},
			fields=["name", "status", "assigned_to", "modified"],
			order_by="creation desc",
		),
		"repair_jobs": frappe.get_all(
			"Repair Job",
			filters={"service_request": service_request},
			fields=["name", "status", "assigned_to", "job_type", "modified"],
			order_by="creation desc",
		),
	}


def on_sales_invoice_submit(doc, method=None):
	request_name = getattr(doc, "service_request", None)
	if request_name and frappe.db.exists("Service Request", request_name):
		frappe.db.set_value(
			"Service Request", request_name, {"sales_invoice": doc.name, "status": "Invoiced"}
		)
		return

	job_name = getattr(doc, "service_job", None)
	if job_name and frappe.db.exists("Service Request", {"source_service_job": job_name}):
		sr = frappe.db.get_value("Service Request", {"source_service_job": job_name}, "name")
		frappe.db.set_value("Service Request", sr, {"sales_invoice": doc.name, "status": "Invoiced"})


def on_sales_invoice_cancel(doc, method=None):
	request_name = getattr(doc, "service_request", None)
	if request_name and frappe.db.exists("Service Request", request_name):
		req = frappe.get_doc("Service Request", request_name)
		status = "Completed" if req.status == "Invoiced" else req.status
		frappe.db.set_value("Service Request", request_name, {"sales_invoice": None, "status": status})
		return

	job_name = getattr(doc, "service_job", None)
	if job_name and frappe.db.exists("Service Request", {"source_service_job": job_name}):
		sr = frappe.db.get_value("Service Request", {"source_service_job": job_name}, "name")
		req = frappe.get_doc("Service Request", sr)
		status = "Completed" if req.status == "Invoiced" else req.status
		frappe.db.set_value("Service Request", sr, {"sales_invoice": None, "status": status})
