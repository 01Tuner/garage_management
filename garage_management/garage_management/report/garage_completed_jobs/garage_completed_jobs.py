# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Service Request", "fieldname": "name", "fieldtype": "Link", "options": "Service Request", "width": 140},
		{"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Components", "fieldname": "components", "fieldtype": "Data", "width": 200},
		{"label": "Invoice", "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 130},
		{"label": "Billing Total", "fieldname": "billing_total", "fieldtype": "Currency", "width": 120},
		{"label": "Modified", "fieldname": "modified", "fieldtype": "Datetime", "width": 150},
	]
	conditions = {"status": ["in", ["Completed", "Invoiced", "Delivered"]], "docstatus": ["<", 2]}
	if filters.get("from_date"):
		conditions["modified"] = [">=", getdate(filters.from_date)]
	data = frappe.get_all(
		"Service Request",
		filters=conditions,
		fields=["name", "customer_name", "status", "sales_invoice", "billing_total", "modified"],
		order_by="modified desc",
	)
	if filters.get("to_date"):
		to_date = getdate(filters.to_date)
		data = [d for d in data if getdate(d.modified) <= to_date]
	for job in data:
		comps = frappe.get_all(
			"Service Request Component",
			filters={"parent": job.name},
			fields=["repair_asset", "serial_number"],
		)
		job.components = ", ".join(
			f"{c.repair_asset or ''} ({c.serial_number})" if c.serial_number else (c.repair_asset or "")
			for c in comps
		)
	return columns, data
