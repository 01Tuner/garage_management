# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from garage_management.permissions import assigned_doc_has_permission, assigned_doc_query_conditions


class Inspection(Document):
	def before_insert(self):
		if not self.assigned_to:
			self.assigned_to = frappe.session.user
		self.pull_request_parts_if_empty()

	def validate(self):
		self.sync_fetched_fields()

	def on_update(self):
		self.bump_parent_status()

	def sync_fetched_fields(self):
		if not self.service_request:
			return
		values = frappe.db.get_value(
			"Service Request",
			self.service_request,
			["customer", "customer_name", "company"],
			as_dict=True,
		)
		if values:
			self.customer = values.customer
			self.customer_name = values.customer_name
			self.company = values.company

	def pull_request_parts_if_empty(self):
		if self.part_results or not self.service_request:
			return
		components = frappe.get_all(
			"Service Request Component",
			filters={"parent": self.service_request},
			fields=["repair_asset", "serial_number", "make_type", "part_no"],
			order_by="idx",
		)
		for row in components:
			self.append("part_results", row)

	def bump_parent_status(self):
		if self.flags.skip_request_sync:
			return
		if not self.service_request or self.status == "Cancelled":
			return
		parent_status = frappe.db.get_value("Service Request", self.service_request, "status")
		if parent_status == "Received":
			frappe.db.set_value("Service Request", self.service_request, "status", "Inspecting")

	@frappe.whitelist()
	def create_repair_job(self, assigned_to=None):
		if self.is_new():
			frappe.throw(_("Save the Inspection first"))
		sr = frappe.get_doc("Service Request", self.service_request)
		return sr.create_repair_job(assigned_to=assigned_to or self.assigned_to, inspection=self.name)


@frappe.whitelist()
def create_repair_job(inspection, assigned_to=None):
	insp = frappe.get_doc("Inspection", inspection)
	return insp.create_repair_job(assigned_to=assigned_to)


def get_permission_query_conditions(user=None):
	return assigned_doc_query_conditions("Inspection", user)


def has_permission(doc, ptype=None, user=None):
	return assigned_doc_has_permission(doc, user)
