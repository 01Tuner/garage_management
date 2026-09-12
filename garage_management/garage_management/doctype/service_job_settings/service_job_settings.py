# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceJobSettings(Document):
	pass


def get_settings():
	return frappe.get_single("Service Job Settings")


@frappe.whitelist()
def get_default_letter_head():
	return (
		frappe.db.get_single_value("Service Job Settings", "default_letter_head")
		or frappe.db.get_single_value("Service Job Settings", "letter_head")
		or frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0}, "name")
		or frappe.db.get_value("Letter Head", {"is_default": 1}, "name")
		or None
	)
