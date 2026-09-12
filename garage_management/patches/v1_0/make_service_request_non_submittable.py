import frappe


def execute():
	"""Reset any submitted or cancelled Service Requests to docstatus = 0."""
	if frappe.db.table_exists("Service Request"):
		frappe.db.sql(
			"""
			UPDATE `tabService Request`
			SET docstatus = 0
			WHERE docstatus != 0
		"""
		)
