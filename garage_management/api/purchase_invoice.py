# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def validate_purchase_invoice(doc, method=None):
	"""Auto-sync service_request from repair_job and propagate to items table."""
	if getattr(doc, "repair_job", None) and not getattr(doc, "service_request", None):
		sr = frappe.db.get_value("Repair Job", doc.repair_job, "service_request")
		if sr:
			doc.service_request = sr

	sr = getattr(doc, "service_request", None)
	rj = getattr(doc, "repair_job", None)

	if hasattr(doc, "items") and (sr or rj):
		for row in doc.items:
			if sr and hasattr(row, "service_request") and not row.service_request:
				row.service_request = sr
			if rj and hasattr(row, "repair_job") and not row.repair_job:
				row.repair_job = rj


def validate_purchase_order(doc, method=None):
	"""Propagate service_request to Purchase Order items table."""
	sr = getattr(doc, "service_request", None)
	if sr and hasattr(doc, "items"):
		for row in doc.items:
			if hasattr(row, "service_request") and not row.service_request:
				row.service_request = sr


@frappe.whitelist()
def get_service_request_purchases(service_request):
	"""Return all active Purchase Invoices and Sales Revenue info linked to this Service Request."""
	if not service_request:
		return {"invoices": [], "total_net": 0.0, "total_grand": 0.0, "count": 0, "sales": {}}

	# Find invoices linked at header level or item level
	invoices = frappe.db.sql(
		"""
		SELECT DISTINCT
			pi.name,
			pi.supplier,
			pi.posting_date,
			pi.base_net_total AS net_total,
			pi.base_grand_total AS grand_total,
			pi.status,
			pi.docstatus,
			IFNULL(pi.repair_job, '') AS repair_job
		FROM `tabPurchase Invoice` pi
		LEFT JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE (pi.service_request = %(sr)s OR pii.service_request = %(sr)s)
			AND pi.docstatus < 2
		ORDER BY pi.posting_date DESC, pi.creation DESC
		""",
		{"sr": service_request},
		as_dict=True,
	)

	total_net = sum(flt(inv.net_total) for inv in invoices)
	total_grand = sum(flt(inv.grand_total) for inv in invoices)

	# Fetch Commercial Documents for this Service Request
	sr_doc = frappe.get_doc("Service Request", service_request)

	# 1. Sales Invoices
	sales_invoices = frappe.db.sql(
		"""
		SELECT name, base_net_total AS net_total, base_grand_total AS grand_total, status, docstatus, posting_date
		FROM `tabSales Invoice`
		WHERE (service_request = %(sr)s OR name = %(si)s) AND docstatus < 2
		ORDER BY posting_date DESC, creation DESC
		""",
		{"sr": service_request, "si": sr_doc.sales_invoice or ""},
		as_dict=True,
	)

	# 2. Sales Orders
	sales_orders = frappe.db.sql(
		"""
		SELECT name, base_net_total AS net_total, base_grand_total AS grand_total, status, docstatus, transaction_date
		FROM `tabSales Order`
		WHERE (service_request = %(sr)s OR name = %(so)s) AND docstatus < 2
		ORDER BY transaction_date DESC, creation DESC
		""",
		{"sr": service_request, "so": sr_doc.sales_order or ""},
		as_dict=True,
	)

	# 3. Quotations
	quotations = frappe.db.sql(
		"""
		SELECT name, base_net_total AS net_total, base_grand_total AS grand_total, status, docstatus, transaction_date
		FROM `tabQuotation`
		WHERE (service_request = %(sr)s OR name = %(q)s) AND docstatus < 2
		ORDER BY transaction_date DESC, creation DESC
		""",
		{"sr": service_request, "q": sr_doc.quotation or ""},
		as_dict=True,
	)

	# Determine True Revenue
	if sales_invoices:
		revenue_net = sum(flt(s.net_total) for s in sales_invoices)
		revenue_grand = sum(flt(s.grand_total) for s in sales_invoices)
		revenue_source = "Sales Invoice"
	elif sales_orders:
		revenue_net = sum(flt(s.net_total) for s in sales_orders)
		revenue_grand = sum(flt(s.grand_total) for s in sales_orders)
		revenue_source = "Sales Order"
	else:
		revenue_net = flt(sr_doc.billing_total or 0)
		revenue_grand = flt(quotations[0].grand_total) if quotations else revenue_net
		revenue_source = "Quotation (Estimated)"

	return {
		"invoices": invoices,
		"total_net": total_net,
		"total_grand": total_grand,
		"count": len(invoices),
		"sales": {
			"revenue_net": revenue_net,
			"revenue_grand": revenue_grand,
			"revenue_source": revenue_source,
			"sales_invoices": sales_invoices,
			"sales_orders": sales_orders,
			"quotations": quotations,
		},
	}


@frappe.whitelist()
def get_service_request_procurement_summary(service_request):
	"""Return comprehensive procurement details: Customer PO, parts needed, warehouse stock, POs, and PIs."""
	if not service_request or not frappe.db.exists("Service Request", service_request):
		return {}

	sr = frappe.get_doc("Service Request", service_request)

	# 1. Customer PO & Sales Order Info
	so_info = None
	if sr.sales_order and frappe.db.exists("Sales Order", sr.sales_order):
		so = frappe.get_doc("Sales Order", sr.sales_order)
		so_info = {
			"name": so.name,
			"status": so.status,
			"customer_po_no": so.po_no or sr.get("customer_po_no") or "",
			"customer_po_date": str(so.po_date or sr.get("customer_po_date") or ""),
			"grand_total": flt(so.grand_total),
			"docstatus": so.docstatus,
		}
		if so.po_no and not sr.get("customer_po_no"):
			sr.db_set("customer_po_no", so.po_no, update_modified=False)
		if so.po_date and not sr.get("customer_po_date"):
			sr.db_set("customer_po_date", so.po_date, update_modified=False)

	# 2. Linked Purchase Orders
	pos = frappe.db.sql(
		"""
		SELECT DISTINCT
			po.name,
			po.supplier,
			po.transaction_date,
			po.base_grand_total AS grand_total,
			po.status,
			po.docstatus
		FROM `tabPurchase Order` po
		LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE (po.service_request = %(sr)s OR poi.service_request = %(sr)s)
			AND po.docstatus < 2
		ORDER BY po.transaction_date DESC, po.creation DESC
		""",
		{"sr": service_request},
		as_dict=True,
	)

	# 3. Linked Purchase Invoices
	pis = get_service_request_purchases(service_request).get("invoices", [])

	# 4. Required Parts Collection Tracking
	parts = []
	seen_items = set()

	# Pull parts from Billing Items
	for row in sr.get("billing_items", []):
		if not row.item_code or row.item_code in seen_items:
			continue
		is_stock = frappe.db.get_value("Item", row.item_code, "is_stock_item")
		# Only track stock items / spare parts
		if is_stock:
			seen_items.add(row.item_code)
			# Check stock in warehouse
			default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse") or "Stores - D"
			actual_qty = frappe.db.get_value(
				"Bin", {"item_code": row.item_code, "warehouse": default_wh}, "actual_qty"
			) or frappe.db.sql(
				"SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s", (row.item_code,)
			)[0][0] or 0.0

			# Check if ordered in PO
			po_ordered_qty = frappe.db.sql(
				"""
				SELECT SUM(poi.qty)
				FROM `tabPurchase Order Item` poi
				JOIN `tabPurchase Order` po ON po.name = poi.parent
				WHERE poi.item_code = %s AND (po.service_request = %s OR poi.service_request = %s) AND po.docstatus = 1
				""",
				(row.item_code, service_request, service_request),
			)[0][0] or 0.0

			# Check if received in PI
			pi_received_qty = frappe.db.sql(
				"""
				SELECT SUM(pii.qty)
				FROM `tabPurchase Invoice Item` pii
				JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
				WHERE pii.item_code = %s AND (pi.service_request = %s OR pii.service_request = %s) AND pi.docstatus = 1
				""",
				(row.item_code, service_request, service_request),
			)[0][0] or 0.0

			is_ready = flt(actual_qty) >= flt(row.qty) or flt(pi_received_qty) >= flt(row.qty)

			stock_uom = row.get("uom") or frappe.db.get_value("Item", row.item_code, "stock_uom") or "Nos"

			parts.append({
				"item_code": row.item_code,
				"item_name": row.item_name or row.item_code,
				"qty_required": flt(row.qty),
				"uom": stock_uom,
				"stock_available": flt(actual_qty),
				"po_ordered_qty": flt(po_ordered_qty),
				"pi_received_qty": flt(pi_received_qty),
				"is_ready": bool(is_ready),
			})

	ready_count = sum(1 for p in parts if p["is_ready"])
	total_parts = len(parts)
	readiness_pct = int((ready_count / total_parts) * 100) if total_parts > 0 else 100

	return {
		"service_request": sr.name,
		"status": sr.status,
		"customer_po_no": sr.get("customer_po_no") or "",
		"customer_po_date": str(sr.get("customer_po_date") or ""),
		"sales_order": so_info,
		"parts": parts,
		"ready_count": ready_count,
		"total_parts": total_parts,
		"readiness_pct": readiness_pct,
		"purchase_orders": pos,
		"purchase_invoices": pis,
		"total_purchase_cost": sum(flt(p["net_total"]) for p in pis),
	}


@frappe.whitelist()
def mark_parts_ready_for_repair(service_request):
	"""Transition job from Awaiting Parts to Repairing."""
	sr = frappe.get_doc("Service Request", service_request)
	if sr.status not in ("Awaiting Parts", "Quoted", "Awaiting Approval"):
		frappe.msgprint(_("Job is already {0}").format(sr.status), alert=True)
		return {"status": sr.status}

	sr.db_set("status", "Repairing", update_modified=True)
	frappe.msgprint(
		_("Parts marked as ready. Service Request {0} moved to Repairing").format(sr.name),
		indicator="green",
		alert=True,
	)
	return {"status": "Repairing"}


@frappe.whitelist()
def unlink_purchase_invoice(purchase_invoice, service_request=None):
	"""Unlink a Purchase Invoice from a Service Request."""
	if not frappe.db.exists("Purchase Invoice", purchase_invoice):
		frappe.throw(_("Purchase Invoice {0} not found").format(purchase_invoice))

	pi = frappe.get_doc("Purchase Invoice", purchase_invoice)
	if hasattr(pi, "service_request"):
		frappe.db.set_value("Purchase Invoice", purchase_invoice, "service_request", None, update_modified=False)
	if hasattr(pi, "repair_job"):
		frappe.db.set_value("Purchase Invoice", purchase_invoice, "repair_job", None, update_modified=False)

	if frappe.db.has_column("Purchase Invoice Item", "service_request"):
		frappe.db.sql(
			"""
			UPDATE `tabPurchase Invoice Item`
			SET service_request = NULL, repair_job = NULL
			WHERE parent = %s
			""",
			(purchase_invoice,),
		)

	frappe.msgprint(
		_("Purchase Invoice {0} unlinked successfully").format(purchase_invoice),
		indicator="green",
		alert=True,
	)
	return {"unlinked": purchase_invoice}


@frappe.whitelist()
def unlink_purchase_order(purchase_order, service_request=None):
	"""Unlink a Purchase Order from a Service Request."""
	if not frappe.db.exists("Purchase Order", purchase_order):
		frappe.throw(_("Purchase Order {0} not found").format(purchase_order))

	if hasattr(frappe.get_meta("Purchase Order"), "service_request"):
		frappe.db.set_value("Purchase Order", purchase_order, "service_request", None, update_modified=False)

	if frappe.db.has_column("Purchase Order Item", "service_request"):
		frappe.db.sql(
			"""
			UPDATE `tabPurchase Order Item`
			SET service_request = NULL
			WHERE parent = %s
			""",
			(purchase_order,),
		)

	frappe.msgprint(
		_("Purchase Order {0} unlinked successfully").format(purchase_order),
		indicator="green",
		alert=True,
	)
	return {"unlinked": purchase_order}


@frappe.whitelist()
def link_purchase_invoice(purchase_invoice, service_request, repair_job=None):
	"""Link an existing Purchase Invoice to a Service Request and optional Repair Job."""
	if not frappe.db.exists("Purchase Invoice", purchase_invoice):
		frappe.throw(_("Purchase Invoice {0} not found").format(purchase_invoice))
	if not frappe.db.exists("Service Request", service_request):
		frappe.throw(_("Service Request {0} not found").format(service_request))

	updates = {"service_request": service_request}
	if repair_job:
		updates["repair_job"] = repair_job

	frappe.db.set_value("Purchase Invoice", purchase_invoice, updates, update_modified=False)

	if frappe.db.has_column("Purchase Invoice Item", "service_request"):
		frappe.db.sql(
			"""
			UPDATE `tabPurchase Invoice Item`
			SET service_request = %s, repair_job = %s
			WHERE parent = %s
			""",
			(service_request, repair_job, purchase_invoice),
		)

	frappe.msgprint(
		_("Purchase Invoice {0} linked to Service Request {1}").format(purchase_invoice, service_request),
		indicator="green",
		alert=True,
	)
	return {"linked": purchase_invoice}

