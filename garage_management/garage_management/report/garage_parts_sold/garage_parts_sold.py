# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
	]

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	data = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			sii.item_name,
			SUM(sii.qty) AS qty,
			SUM(sii.amount) AS amount,
			COUNT(DISTINCT si.name) AS invoice_count
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		WHERE si.docstatus = 1
			AND IFNULL(si.service_request, '') != ''
			AND i.is_stock_item = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY sii.item_code, sii.item_name
		ORDER BY qty DESC
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	return columns, data
