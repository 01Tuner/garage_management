# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = [
		{"label": "Serial Number", "fieldname": "serial_number", "fieldtype": "Data", "width": 140},
		{"label": "Repair Asset", "fieldname": "repair_asset", "fieldtype": "Link", "options": "Part Type", "width": 120},
		{"label": "Customer", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": "Visit Count", "fieldname": "visit_count", "fieldtype": "Int", "width": 100},
		{"label": "Requests", "fieldname": "jobs", "fieldtype": "Data", "width": 260},
	]

	data = frappe.db.sql(
		"""
		SELECT
			c.serial_number,
			MAX(c.repair_asset) AS repair_asset,
			MAX(j.customer_name) AS customer_name,
			COUNT(DISTINCT j.name) AS visit_count,
			GROUP_CONCAT(DISTINCT j.name ORDER BY j.received_date SEPARATOR ', ') AS jobs
		FROM `tabService Request Component` c
		INNER JOIN `tabService Request` j ON j.name = c.parent
		WHERE IFNULL(c.serial_number, '') != ''
			AND j.docstatus < 2
			AND j.status != 'Cancelled'
		GROUP BY c.serial_number
		HAVING COUNT(DISTINCT j.name) > 1
		ORDER BY visit_count DESC
		""",
		as_dict=True,
	)
	return columns, data
