# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


def is_garage_technician_only(user=None):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return False
	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return False
	if "Garage Technician" not in roles:
		return False
	return not any(r in roles for r in ("Garage Manager", "Garage Front Desk", "Accounts User"))


def assigned_doc_query_conditions(doctype, user=None):
	if not user:
		user = frappe.session.user
	if not is_garage_technician_only(user):
		return None
	return f"`tab{doctype}`.assigned_to = {frappe.db.escape(user)}"


def assigned_doc_has_permission(doc, user=None):
	if not user:
		user = frappe.session.user
	if not is_garage_technician_only(user):
		return True
	return doc.assigned_to == user
