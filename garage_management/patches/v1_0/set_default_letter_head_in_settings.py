import frappe


def execute():
	if not frappe.db.exists("DocType", "Service Job Settings"):
		return

	settings = frappe.get_single("Service Job Settings")
	if not settings.get("default_letter_head"):
		default_lh = (
			frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0}, "name")
			or frappe.db.get_value("Letter Head", {"is_default": 1}, "name")
		)
		if default_lh:
			frappe.db.set_single_value("Service Job Settings", "default_letter_head", default_lh)
