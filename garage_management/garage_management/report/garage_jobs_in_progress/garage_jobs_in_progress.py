# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Service Request", "fieldname": "name", "fieldtype": "Link", "options": "Service Request", "width": 140},
		{"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": "Components", "fieldname": "components", "fieldtype": "Data", "width": 200},
		{"label": "Inspections", "fieldname": "inspections", "fieldtype": "Int", "width": 100},
		{"label": "Repair Jobs", "fieldname": "repair_jobs", "fieldtype": "Int", "width": 100},
		{"label": "Priority", "fieldname": "priority", "fieldtype": "Data", "width": 90},
		{"label": "Received", "fieldname": "received_date", "fieldtype": "Datetime", "width": 150},
	]
	jobs = frappe.get_all(
		"Service Request",
		filters={
			"status": [
				"in",
				[
					"Received",
					"Inspecting",
					"Quoted",
					"Awaiting Approval",
					"In Progress",
					"Testing",
					"On Hold",
				],
			],
			"docstatus": ["<", 2],
		},
		fields=["name", "customer_name", "status", "priority", "received_date"],
		order_by="received_date desc",
	)
	for job in jobs:
		comps = frappe.get_all(
			"Service Request Component",
			filters={"parent": job.name},
			fields=["repair_asset", "serial_number"],
		)
		job.components = ", ".join(
			f"{c.repair_asset or ''} ({c.serial_number})" if c.serial_number else (c.repair_asset or "")
			for c in comps
		)
		job.inspections = frappe.db.count("Inspection", {"service_request": job.name, "status": ["!=", "Cancelled"]})
		job.repair_jobs = frappe.db.count("Repair Job", {"service_request": job.name, "status": ["!=", "Cancelled"]})
	return columns, jobs
