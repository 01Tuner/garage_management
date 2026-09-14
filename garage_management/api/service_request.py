# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate


def _get_request(name):
	doc = frappe.get_doc("Service Request", name)
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
def get_customer_address_display(customer: str) -> str:
	"""Fetch primary address or any linked address for a customer formatted for display."""
	if not customer:
		return ""

	cust_data = frappe.db.get_value(
		"Customer",
		customer,
		["customer_primary_address", "primary_address"],
		as_dict=True,
	)
	if cust_data and cust_data.primary_address:
		return cust_data.primary_address.strip()

	address_name = cust_data.customer_primary_address if cust_data else None

	if not address_name:
		from frappe.contacts.doctype.address.address import get_default_address

		address_name = get_default_address("Customer", customer, sort_key="is_primary_address")

	if not address_name:
		address_name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
			"parent",
		)

	if address_name:
		from frappe.contacts.doctype.address.address import get_address_display

		try:
			display = get_address_display(address_name)
			if display and display.strip():
				return display.strip()
		except Exception:
			pass

		addr = frappe.db.get_value(
			"Address",
			address_name,
			["address_line1", "address_line2", "city", "state", "pincode", "country"],
			as_dict=True,
		)
		if addr:
			parts = [
				addr.address_line1,
				addr.address_line2,
				addr.city,
				addr.state,
				addr.pincode,
				addr.country,
			]
			return ", ".join([p.strip() for p in parts if p and p.strip()])

	return ""


@frappe.whitelist()
def get_customer_contact_details(customer: str) -> dict:
	"""Fetch contact details for a customer from customer creation/contact records."""
	if not customer:
		return {
			"contact_details": "",
			"contact_person": "",
			"mobile_no": "",
			"email_id": "",
		}

	cust = frappe.db.get_value(
		"Customer",
		customer,
		["customer_primary_contact", "mobile_no", "email_id"],
		as_dict=True,
	) or {}

	contact_name = cust.get("customer_primary_contact")

	if not contact_name:
		from frappe.contacts.doctype.contact.contact import get_default_contact

		try:
			contact_name = get_default_contact("Customer", customer)
		except Exception:
			contact_name = None

	if not contact_name:
		contacts = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": customer,
				"parenttype": "Contact",
			},
			pluck="parent",
			limit=1,
		)
		if contacts:
			contact_name = contacts[0]

	contact_person = contact_name or ""
	full_name = ""
	mobile_no = cust.get("mobile_no") or ""
	email_id = cust.get("email_id") or ""
	phone = ""
	designation = ""

	if contact_name and frappe.db.exists("Contact", contact_name):
		con = frappe.get_doc("Contact", contact_name)
		full_name = (
			con.get("full_name")
			or " ".join(filter(None, [con.get("first_name"), con.get("last_name")]))
		)
		mobile_no = con.get("mobile_no") or mobile_no
		if not mobile_no and hasattr(con, "phone_nos"):
			for p in con.phone_nos or []:
				if p.get("phone"):
					mobile_no = p.get("phone")
					break

		email_id = con.get("email_id") or email_id
		if not email_id and hasattr(con, "email_ids"):
			for e in con.email_ids or []:
				if e.get("email_id"):
					email_id = e.get("email_id")
					break

		phone = con.get("phone") or ""
		designation = con.get("designation") or ""

	lines = []
	if full_name:
		line = full_name
		if designation:
			line += f" ({designation})"
		lines.append(line)
	if mobile_no:
		lines.append(f"Mobile: {mobile_no}")
	if phone and phone != mobile_no:
		lines.append(f"Phone: {phone}")
	if email_id:
		lines.append(f"Email: {email_id}")

	contact_display = "\n".join(lines).strip()

	return {
		"contact_details": contact_display,
		"contact_person": contact_person,
		"mobile_no": mobile_no,
		"email_id": email_id,
	}


@frappe.whitelist()
def get_customer_contact_and_address(customer: str) -> dict:
	"""Combined helper to fetch both contact details and formatted address for a customer."""
	addr_display = get_customer_address_display(customer)
	contact_info = get_customer_contact_details(customer)
	contact_info["address_display"] = addr_display
	return contact_info


@frappe.whitelist()
def create_quotation(service_request):
	req = _get_request(service_request)
	if req.quotation and frappe.db.exists("Quotation", req.quotation):
		frappe.throw(_("Quotation {0} already linked").format(req.quotation))

	# If billing items is empty, try to auto-sync from repair job or inspection
	if not req.billing_items:
		sync_repair_job_parts_to_billing(service_request)
		req.reload()
	if not req.billing_items:
		sync_inspection_items_to_billing(service_request)
		req.reload()

	if not req.billing_items:
		frappe.throw(_("Add Billing Items on the Service Request before creating Quotation"))

	settings = _settings()
	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = req.customer
	quotation.company = req.company
	quotation.transaction_date = nowdate()
	quotation.order_type = "Sales"
	if settings.default_price_list:
		quotation.selling_price_list = settings.default_price_list
	tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": req.company, "is_default": 1}
	)
	if tax_template:
		quotation.taxes_and_charges = tax_template

	if hasattr(quotation, "service_request"):
		quotation.service_request = req.name

	for row in req.billing_items:
		quotation.append("items", _item_row_from_billing(row))

	quotation.run_method("set_missing_values")
	quotation.set_taxes()
	quotation.run_method("calculate_taxes_and_totals")

	# Create as Draft (docstatus = 0) so user can review and edit
	quotation.insert(ignore_permissions=True)

	req.db_set({"quotation": quotation.name, "status": "Quoted"}, update_modified=True)
	frappe.msgprint(_("Quotation {0} created as Draft").format(quotation.name), indicator="green", alert=True)
	return quotation.name


@frappe.whitelist()
def mark_customer_approved(service_request):
	req = frappe.get_doc("Service Request", service_request)
	if req.quotation and frappe.db.exists("Quotation", req.quotation):
		qdoc = frappe.get_doc("Quotation", req.quotation)
		if qdoc.docstatus == 0:
			try:
				qdoc.flags.ignore_permissions = True
				qdoc.submit()
			except Exception:
				pass

	updates = {"status": "Repairing"}
	req.db_set(updates, update_modified=True)
	frappe.msgprint(_("Customer approved — Service Request is Repairing"), indicator="green", alert=True)
	return req.name


@frappe.whitelist()
def mark_service_completed(service_request):
	req = frappe.get_doc("Service Request", service_request)
	req.db_set("status", "Completed", update_modified=True)
	frappe.msgprint(_("Service Request marked as Completed"), indicator="green", alert=True)
	return req.name


@frappe.whitelist()
def mark_delivered(service_request):
	req = frappe.get_doc("Service Request", service_request)
	req.db_set("status", "Delivered", update_modified=True)
	frappe.msgprint(_("Service Request marked as Delivered"), indicator="green", alert=True)
	return req.name


@frappe.whitelist()
def sync_inspection_items_to_billing(service_request):
	req = frappe.get_doc("Service Request", service_request)
	inspections = frappe.get_all(
		"Inspection",
		filters={"service_request": service_request, "status": ["!=", "Cancelled"]},
		pluck="name",
	)
	if not inspections:
		return 0

	existing_items = {row.item_code for row in req.billing_items if row.item_code}
	added = 0
	price_list = frappe.db.get_single_value("Service Job Settings", "default_price_list")
	default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse")

	for insp_name in inspections:
		insp = frappe.get_doc("Inspection", insp_name)
		for row in insp.key_replacement_items or []:
			if not row.item_code or row.item_code in existing_items:
				continue
			item_details = frappe.db.get_value(
				"Item",
				row.item_code,
				["item_name", "description", "is_stock_item", "standard_rate"],
				as_dict=True,
			)
			if not item_details:
				continue

			rate = item_details.standard_rate or 0
			if price_list:
				pl_rate = frappe.db.get_value(
					"Item Price",
					{"item_code": row.item_code, "price_list": price_list, "selling": 1},
					"price_list_rate",
				)
				if pl_rate:
					rate = pl_rate

			req.append(
				"billing_items",
				{
					"item_code": row.item_code,
					"item_name": item_details.item_name,
					"description": item_details.description,
					"qty": 1,
					"rate": rate,
					"amount": rate,
					"warehouse": default_wh if item_details.is_stock_item else None,
					"is_stock_item": item_details.is_stock_item,
				},
			)
			existing_items.add(row.item_code)
			added += 1

	if added > 0:
		req.calculate_billing_total()
		req.save(ignore_permissions=True)
		frappe.msgprint(_("Added {0} item(s) from Inspection to Billing Items").format(added), indicator="green", alert=True)

	return added


@frappe.whitelist()
def sync_repair_job_parts_to_billing(service_request):
	"""Sync spare parts used in active Repair Jobs into Service Request billing items."""
	req = frappe.get_doc("Service Request", service_request)
	repair_jobs = frappe.get_all(
		"Repair Job",
		filters={"service_request": service_request, "status": ["!=", "Cancelled"]},
		pluck="name",
	)
	if not repair_jobs:
		return 0

	existing_items = {row.item_code: row for row in req.billing_items if row.item_code}
	added = 0
	updated = 0
	settings = _settings()
	default_wh = settings.default_warehouse

	for rj_name in repair_jobs:
		rj = frappe.get_doc("Repair Job", rj_name)
		for row in rj.spare_parts or []:
			if not row.item_code:
				continue

			item_details = frappe.db.get_value(
				"Item",
				row.item_code,
				["item_name", "description", "is_stock_item", "standard_rate"],
				as_dict=True,
			)
			if not item_details:
				continue

			rate = flt(row.rate) or flt(item_details.standard_rate or 0)
			if not rate and settings.default_price_list:
				pl_rate = frappe.db.get_value(
					"Item Price",
					{"item_code": row.item_code, "price_list": settings.default_price_list, "selling": 1},
					"price_list_rate",
				)
				if pl_rate:
					rate = flt(pl_rate)

			if row.item_code in existing_items:
				b_row = existing_items[row.item_code]
				changed = False
				if flt(row.qty) > flt(b_row.qty):
					b_row.qty = flt(row.qty)
					changed = True
				if not flt(b_row.rate) and rate:
					b_row.rate = rate
					changed = True
				if not b_row.warehouse and (row.warehouse or default_wh):
					b_row.warehouse = row.warehouse or default_wh
					changed = True
				if changed:
					b_row.amount = flt(b_row.qty) * flt(b_row.rate)
					updated += 1
				continue

			req.append(
				"billing_items",
				{
					"item_code": row.item_code,
					"item_name": row.item_name or item_details.item_name,
					"description": row.description or item_details.description,
					"qty": flt(row.qty or 1),
					"rate": rate,
					"amount": flt(row.qty or 1) * rate,
					"warehouse": row.warehouse or (default_wh if item_details.is_stock_item else None),
					"is_stock_item": item_details.is_stock_item,
				},
			)
			existing_items[row.item_code] = req.billing_items[-1]
			added += 1

	if added > 0 or updated > 0:
		req.calculate_billing_total()
		req.save(ignore_permissions=True)

	return added + updated


def _get_repair_job_parts(service_request):
	"""Fetch all spare parts logged across active (non-cancelled) Repair Jobs."""
	jobs = frappe.get_all(
		"Repair Job",
		filters={"service_request": service_request, "status": ["!=", "Cancelled"]},
		pluck="name",
	)
	parts = []
	for j_name in jobs:
		job_doc = frappe.get_doc("Repair Job", j_name)
		for p in job_doc.spare_parts or []:
			if p.item_code:
				parts.append({
					"repair_job": j_name,
					"item_code": p.item_code,
					"item_name": p.item_name,
					"description": p.description,
					"qty": flt(p.qty or 1),
					"rate": flt(p.rate or 0),
					"amount": flt(p.amount or 0),
					"uom": p.uom,
					"warehouse": p.warehouse,
					"serial_no": getattr(p, "serial_no", None),
					"batch_no": getattr(p, "batch_no", None),
				})
	return parts


@frappe.whitelist()
def create_sales_order(service_request):
	req = _get_request(service_request)
	if req.sales_order and frappe.db.exists("Sales Order", req.sales_order):
		frappe.throw(_("Sales Order {0} already linked").format(req.sales_order))

	sync_repair_job_parts_to_billing(service_request)
	req.reload()

	settings = _settings()
	so = None

	if req.quotation and frappe.db.exists("Quotation", req.quotation):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		# Ensure quotation is submitted before making Sales Order
		qdoc = frappe.get_doc("Quotation", req.quotation)
		if qdoc.docstatus == 0:
			qdoc.flags.ignore_permissions = True
			qdoc.submit()

		so = make_sales_order(req.quotation)
	elif req.billing_items:
		so = frappe.new_doc("Sales Order")
		so.customer = req.customer
		so.company = req.company
		so.transaction_date = nowdate()
		so.delivery_date = nowdate()
		if settings.default_price_list:
			so.selling_price_list = settings.default_price_list
		tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": req.company, "is_default": 1}
		)
		if tax_template:
			so.taxes_and_charges = tax_template
		for row in req.billing_items:
			so.append("items", _item_row_from_billing(row))
		so.run_method("set_missing_values")
		so.set_taxes()
		so.run_method("calculate_taxes_and_totals")
	else:
		frappe.throw(_("Add items to Service Request, complete Repair Job spare parts, or create Quotation first"))

	if hasattr(so, "delivery_date") and not so.delivery_date:
		so.delivery_date = nowdate()
	for item in getattr(so, "items", []):
		if not getattr(item, "delivery_date", None):
			item.delivery_date = so.delivery_date or nowdate()

	if req.get("customer_po_no") and hasattr(so, "po_no") and not so.po_no:
		so.po_no = req.customer_po_no
	if req.get("customer_po_date") and hasattr(so, "po_date") and not so.po_date:
		so.po_date = req.customer_po_date

	if hasattr(so, "service_request"):
		so.service_request = req.name
	so.insert(ignore_permissions=True)

	# Determine next status: if there are stock parts, move to Awaiting Parts, otherwise In Progress
	has_parts = False
	for row in req.billing_items or []:
		if row.item_code and frappe.db.get_value("Item", row.item_code, "is_stock_item"):
			has_parts = True
			break

	next_status = "Awaiting Parts" if has_parts else "Repairing"

	updates = {
		"sales_order": so.name,
		"status": next_status,
	}
	if hasattr(so, "po_no") and so.po_no:
		updates["customer_po_no"] = so.po_no
	if hasattr(so, "po_date") and so.po_date:
		updates["customer_po_date"] = so.po_date

	req.db_set(updates, update_modified=True)
	frappe.msgprint(_("Sales Order {0} created. Status: {1}").format(so.name, next_status), indicator="green", alert=True)
	return so.name


@frappe.whitelist()
def create_sales_invoice(service_request):
	req = _get_request(service_request)
	if req.sales_invoice and frappe.db.exists("Sales Invoice", req.sales_invoice):
		frappe.throw(_("Sales Invoice {0} already linked").format(req.sales_invoice))

	# First, sync any spare parts from Repair Jobs to Billing Items
	sync_repair_job_parts_to_billing(service_request)
	req.reload()

	settings = _settings()
	default_wh = settings.default_warehouse
	si = None

	if req.sales_order and frappe.db.exists("Sales Order", req.sales_order):
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		so_doc = frappe.get_doc("Sales Order", req.sales_order)
		if so_doc.docstatus == 0:
			try:
				so_doc.flags.ignore_permissions = True
				so_doc.submit()
			except Exception:
				pass

		si = make_sales_invoice(req.sales_order)

		# If Repair Jobs have parts not present in Sales Order, append them
		existing_items = {item.item_code for item in si.items if item.item_code}
		for b_row in req.billing_items:
			if b_row.item_code and b_row.item_code not in existing_items:
				si.append("items", _item_row_from_billing(b_row))
				existing_items.add(b_row.item_code)
	elif req.quotation and frappe.db.exists("Quotation", req.quotation):
		q_doc = frappe.get_doc("Quotation", req.quotation)
		if q_doc.docstatus == 0:
			try:
				q_doc.flags.ignore_permissions = True
				q_doc.submit()
			except Exception:
				pass

		try:
			from erpnext.selling.doctype.quotation.quotation import make_sales_invoice

			si = make_sales_invoice(req.quotation)
		except Exception:
			si = None

		if not si:
			si = frappe.new_doc("Sales Invoice")
			si.customer = req.customer
			si.company = req.company
			si.posting_date = nowdate()
			if q_doc.selling_price_list or settings.default_price_list:
				si.selling_price_list = q_doc.selling_price_list or settings.default_price_list
			if q_doc.taxes_and_charges or settings.default_taxes_and_charges:
				si.taxes_and_charges = q_doc.taxes_and_charges or settings.default_taxes_and_charges

			existing_items = set()
			if q_doc.items:
				for item in q_doc.items:
					si.append(
						"items",
						{
							"item_code": item.item_code,
							"item_name": item.item_name,
							"description": item.description,
							"qty": item.qty,
							"rate": item.rate,
							"uom": item.uom or frappe.db.get_value("Item", item.item_code, "stock_uom") or "Nos",
							"warehouse": getattr(item, "warehouse", None) or default_wh,
						},
					)
					existing_items.add(item.item_code)

			if q_doc.taxes:
				for tax in q_doc.taxes:
					si.append(
						"taxes",
						{
							"charge_type": tax.charge_type,
							"account_head": tax.account_head,
							"description": tax.description,
							"rate": tax.rate,
							"tax_amount": tax.tax_amount,
						},
					)
			elif si.taxes_and_charges:
				si.set_taxes()

		# Consider items from Repair Jobs / Billing Items
		existing_items = {item.item_code for item in si.items if item.item_code}
		for b_row in req.billing_items:
			if b_row.item_code and b_row.item_code not in existing_items:
				si.append("items", _item_row_from_billing(b_row))
				existing_items.add(b_row.item_code)
			elif b_row.item_code and b_row.item_code in existing_items:
				# If actual quantity used in repair job is higher than quoted, update invoice qty
				for row in si.items:
					if row.item_code == b_row.item_code and flt(b_row.qty) > flt(row.qty):
						row.qty = flt(b_row.qty)

		if not si.items:
			for row in req.billing_items:
				si.append("items", _item_row_from_billing(row))

		if not si.items:
			frappe.throw(_("Add items to Quotation, Service Request, or Repair Job before creating Sales Invoice"))
	else:
		# Direct Invoicing (no Quotation / no Sales Order)
		if not req.billing_items:
			sync_inspection_items_to_billing(service_request)
			req.reload()

		if not req.billing_items:
			frappe.throw(_("Add items to Service Request, complete Repair Job spare parts, or create Quotation first"))

		si = frappe.new_doc("Sales Invoice")
		si.customer = req.customer
		si.company = req.company
		si.posting_date = nowdate()
		tax_template = settings.default_taxes_and_charges or frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": req.company, "is_default": 1}
		)
		if tax_template:
			si.taxes_and_charges = tax_template
		for row in req.billing_items:
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

	if hasattr(si, "service_request"):
		si.service_request = req.name

	si.run_method("calculate_taxes_and_totals")
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


def sync_job_sub_statuses(service_request):
	"""Calculate and store aggregated inspection_status and repair_status on Service Request."""
	if not service_request or not frappe.db.exists("Service Request", service_request):
		return "Pending", "Pending"

	# Calculate Inspection Status
	inspections = frappe.get_all(
		"Inspection",
		filters={"service_request": service_request},
		fields=["status"],
		order_by="creation desc",
	)
	if not inspections:
		inspection_status = "Pending"
	else:
		active = [i.status for i in inspections if i.status != "Cancelled"]
		if any(s == "In Progress" for s in active):
			inspection_status = "In Progress"
		elif active and all(s == "Completed" for s in active):
			inspection_status = "Completed"
		elif any(s == "Draft" for s in active):
			inspection_status = "Draft"
		elif active:
			inspection_status = active[0]
		elif inspections:
			inspection_status = inspections[0].status
		else:
			inspection_status = "Pending"

	# Calculate Repair Status
	repairs = frappe.get_all(
		"Repair Job",
		filters={"service_request": service_request},
		fields=["status"],
		order_by="creation desc",
	)
	if not repairs:
		repair_status = "Pending"
	else:
		active = [r.status for r in repairs if r.status != "Cancelled"]
		if any(s in ("Repairing", "In Progress") for s in active):
			repair_status = "Repairing"
		elif any(s == "Testing" for s in active):
			repair_status = "Testing"
		elif active and all(s == "Completed" for s in active):
			repair_status = "Completed"
		elif any(s == "Draft" for s in active):
			repair_status = "Draft"
		elif active:
			repair_status = active[0]
		elif repairs:
			repair_status = repairs[0].status
		else:
			repair_status = "Pending"

	frappe.db.set_value(
		"Service Request",
		service_request,
		{
			"inspection_status": inspection_status,
			"repair_status": repair_status,
		},
		update_modified=False,
	)
	return inspection_status, repair_status


@frappe.whitelist()
def get_workshop_docs(service_request):
	insp_status, rep_status = sync_job_sub_statuses(service_request)
	return {
		"inspection_status": insp_status,
		"repair_status": rep_status,
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


@frappe.whitelist()
def unlink_quotation(service_request):
	req = frappe.get_doc("Service Request", service_request)
	if not req.quotation:
		frappe.throw(_("No Quotation linked to Service Request {0}").format(service_request))

	old_quotation = req.quotation
	status = "Draft" if req.status in ("Quoted", "Awaiting Approval") else req.status
	req.db_set({"quotation": None, "status": status}, update_modified=True)

	if frappe.db.exists("Quotation", old_quotation):
		if frappe.db.has_column("Quotation", "service_request"):
			frappe.db.set_value("Quotation", old_quotation, "service_request", None, update_modified=False)
		if frappe.db.has_column("Quotation", "service_job"):
			frappe.db.set_value("Quotation", old_quotation, "service_job", None, update_modified=False)

	frappe.msgprint(_("Quotation {0} unlinked from Service Request").format(old_quotation), indicator="green", alert=True)
	return {"unlinked": old_quotation}


@frappe.whitelist()
def unlink_sales_order(service_request):
	req = frappe.get_doc("Service Request", service_request)
	if not req.sales_order:
		frappe.throw(_("No Sales Order linked to Service Request {0}").format(service_request))

	old_so = req.sales_order
	req.db_set({"sales_order": None}, update_modified=True)

	if frappe.db.exists("Sales Order", old_so):
		if frappe.db.has_column("Sales Order", "service_request"):
			frappe.db.set_value("Sales Order", old_so, "service_request", None, update_modified=False)
		if frappe.db.has_column("Sales Order", "service_job"):
			frappe.db.set_value("Sales Order", old_so, "service_job", None, update_modified=False)

	frappe.msgprint(_("Sales Order {0} unlinked from Service Request").format(old_so), indicator="green", alert=True)
	return {"unlinked": old_so}


@frappe.whitelist()
def unlink_sales_invoice(service_request):
	req = frappe.get_doc("Service Request", service_request)
	if not req.sales_invoice:
		frappe.throw(_("No Sales Invoice linked to Service Request {0}").format(service_request))

	old_si = req.sales_invoice
	status = "Completed" if req.status == "Invoiced" else req.status
	req.db_set({"sales_invoice": None, "status": status}, update_modified=True)

	if frappe.db.exists("Sales Invoice", old_si):
		if frappe.db.has_column("Sales Invoice", "service_request"):
			frappe.db.set_value("Sales Invoice", old_si, "service_request", None, update_modified=False)
		if frappe.db.has_column("Sales Invoice", "service_job"):
			frappe.db.set_value("Sales Invoice", old_si, "service_job", None, update_modified=False)

	frappe.msgprint(_("Sales Invoice {0} unlinked from Service Request").format(old_si), indicator="green", alert=True)
	return {"unlinked": old_si}

