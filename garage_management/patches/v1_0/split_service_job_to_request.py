# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


def execute():
	if not frappe.db.exists("DocType", "Service Job"):
		return
	if not frappe.db.exists("DocType", "Service Request"):
		return

	from garage_management.install import setup_custom_fields

	setup_custom_fields()

	jobs = frappe.get_all("Service Job", pluck="name", order_by="creation")
	for name in jobs:
		if frappe.db.exists("Service Request", {"source_service_job": name}):
			continue
		_migrate_job(name)

	_remap_commercial_links()


def _migrate_job(name):
	job = frappe.get_doc("Service Job", name)
	sr = frappe.new_doc("Service Request")
	sr.source_service_job = job.name
	sr.company = job.company
	sr.status = job.status or "Received"
	sr.priority = job.priority or "Normal"
	sr.received_date = job.received_date
	sr.customer = job.customer
	sr.customer_name = job.customer_name
	sr.mobile_no = job.mobile_no
	sr.contact_person = job.contact_person
	sr.customer_address = job.customer_address
	sr.engine_vehicle_notes = job.engine_vehicle_notes
	sr.complaint = job.complaint
	sr.job_type = job.job_type
	sr.warranty_days = job.warranty_days
	sr.warranty_expiry = job.warranty_expiry
	sr.quotation = job.quotation
	sr.sales_order = job.sales_order
	sr.sales_invoice = job.sales_invoice
	sr.billing_total = job.billing_total

	for row in job.components or []:
		sr.append(
			"components",
			{
				"repair_asset": row.repair_asset,
				"serial_number": row.serial_number,
				"make_type": row.make_type,
				"part_no": row.part_no,
			},
		)

	for row in job.billing_items or []:
		sr.append(
			"billing_items",
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"qty": row.qty,
				"rate": row.rate,
				"amount": row.amount,
				"warehouse": row.warehouse,
				"is_stock_item": row.is_stock_item,
			},
		)

	sr.flags.ignore_status_email = True
	sr.flags.ignore_component_check = True
	sr.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	if job.docstatus:
		sr.db_set("docstatus", job.docstatus, update_modified=False)

	insp = frappe.new_doc("Inspection")
	insp.service_request = sr.name
	insp.assigned_to = job.technician or frappe.session.user
	insp.status = _inspection_status(job)
	insp.inspection_notes = job.inspection_notes
	insp.recommended_work = job.recommended_work
	for row in job.components or []:
		insp.append(
			"part_results",
			{
				"repair_asset": row.repair_asset,
				"serial_number": row.serial_number,
				"make_type": row.make_type,
				"part_no": row.part_no,
				"condition": row.condition,
				"test_bench_results": row.test_bench_results,
				"damaged_part_photo": row.damaged_part_photo,
			},
		)
	for row in job.findings or []:
		insp.append("findings", {"inspection_finding": row.inspection_finding})
	for row in job.key_replacement_items or []:
		insp.append("key_replacement_items", {"item_code": row.item_code})
	insp.flags.skip_request_sync = True
	insp.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

	rj = frappe.new_doc("Repair Job")
	rj.flags.skip_request_sync = True
	rj.service_request = sr.name
	rj.inspection = insp.name
	rj.assigned_to = job.technician or frappe.session.user
	rj.job_type = job.job_type
	rj.status = _repair_status(job)
	rj.work_notes = job.recommended_work
	for row in job.qc_items or []:
		rj.append("qc_items", {"test_name": row.test_name, "result": row.result, "notes": row.notes})
	rj.flags.skip_request_sync = True
	rj.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

	# restore parent status after child insert hooks
	sr.db_set("status", job.status or "Received", update_modified=False)


def _inspection_status(job):
	if job.status in ("Received",):
		return "Draft"
	if job.status in ("Inspecting",):
		return "In Progress"
	if job.status == "Cancelled":
		return "Cancelled"
	if job.findings or job.inspection_notes or job.recommended_work:
		return "Completed"
	if job.status in (
		"Quoted",
		"Awaiting Approval",
		"In Progress",
		"Testing",
		"Completed",
		"Invoiced",
		"Delivered",
	):
		return "Completed"
	return "Draft"


def _repair_status(job):
	mapping = {
		"In Progress": "In Progress",
		"Testing": "Testing",
		"Completed": "Completed",
		"Invoiced": "Completed",
		"Delivered": "Completed",
		"Cancelled": "Cancelled",
	}
	return mapping.get(job.status, "Draft")


def _remap_commercial_links():
	for dt in ("Quotation", "Sales Order", "Sales Invoice"):
		if not frappe.db.has_column(dt, "service_request"):
			continue
		if not frappe.db.has_column(dt, "service_job"):
			continue
		frappe.db.sql(
			f"""
			UPDATE `tab{dt}` t
			INNER JOIN `tabService Request` sr ON sr.source_service_job = t.service_job
			SET t.service_request = sr.name
			WHERE IFNULL(t.service_job, '') != ''
				AND IFNULL(t.service_request, '') = ''
			"""
		)

	for dt, field in (
		("Quotation", "quotation"),
		("Sales Order", "sales_order"),
		("Sales Invoice", "sales_invoice"),
	):
		if not frappe.db.has_column(dt, "service_request"):
			continue
		rows = frappe.get_all(dt, filters={"service_request": ["!=", ""]}, fields=["name", "service_request"])
		for row in rows:
			if not frappe.db.get_value("Service Request", row.service_request, field):
				frappe.db.set_value("Service Request", row.service_request, field, row.name, update_modified=False)
