# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceJobSettings(Document):
	pass


def get_settings():
	return frappe.get_single("Service Job Settings")
