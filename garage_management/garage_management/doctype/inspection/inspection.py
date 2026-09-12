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
		self.enforce_photo_stages()
		self.validate_service_request_status()
		if not self.get("letter_head"):
			if self.get("service_request"):
				self.letter_head = frappe.db.get_value("Service Request", self.service_request, "letter_head")
			if not self.get("letter_head"):
				self.letter_head = (
					frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0}, "name")
					or frappe.db.get_value("Letter Head", {"is_default": 1}, "name")
				)

	def on_update(self):
		self.bump_parent_status()
		if self.service_request:
			from garage_management.api.service_request import sync_job_sub_statuses

			sync_job_sub_statuses(self.service_request)

	def on_trash(self):
		if self.service_request:
			from garage_management.api.service_request import sync_job_sub_statuses

			sync_job_sub_statuses(self.service_request)

	def sync_fetched_fields(self):
		if not self.service_request:
			return
		values = frappe.db.get_value(
			"Service Request",
			self.service_request,
			["customer", "customer_name", "company", "status"],
			as_dict=True,
		)
		if values:
			self.customer = values.customer
			self.customer_name = values.customer_name
			self.company = values.company

	def enforce_photo_stages(self):
		"""Ensure all photos in Inspection are tagged as Inspection stage."""
		for row in self.photos or []:
			row.stage = "Inspection"

	def validate_service_request_status(self):
		"""Prevent creating/editing inspection on a cancelled Service Request."""
		if not self.service_request:
			return
		sr_status = frappe.db.get_value("Service Request", self.service_request, "status")
		if sr_status == "Cancelled":
			frappe.throw(_("Cannot create/update an Inspection for a Cancelled Service Request"))

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
	def complete_inspection(self):
		self.db_set("status", "Completed", update_modified=True)
		# Also sync key replacement items to billing if needed
		if self.service_request:
			from garage_management.api.service_request import sync_inspection_items_to_billing

			sync_inspection_items_to_billing(self.service_request)
		frappe.msgprint(_("Inspection {0} marked as Completed").format(self.name), indicator="green", alert=True)
		return self.name

	@frappe.whitelist()
	def sync_to_billing(self):
		if not self.service_request:
			frappe.throw(_("No Service Request linked"))
		from garage_management.api.service_request import sync_inspection_items_to_billing

		return sync_inspection_items_to_billing(self.service_request)


@frappe.whitelist()
def create_repair_job(inspection, assigned_to=None):
	insp = frappe.get_doc("Inspection", inspection)
	return insp.create_repair_job(assigned_to=assigned_to)


def get_permission_query_conditions(user=None):
	return assigned_doc_query_conditions("Inspection", user)


def has_permission(doc, ptype=None, user=None):
	return assigned_doc_has_permission(doc, user)
