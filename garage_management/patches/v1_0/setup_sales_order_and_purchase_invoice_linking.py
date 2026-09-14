# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from garage_management.install import create_workspace_artifacts, setup_custom_fields


def execute():
	setup_custom_fields()
	create_workspace_artifacts()
	frappe.clear_cache()
