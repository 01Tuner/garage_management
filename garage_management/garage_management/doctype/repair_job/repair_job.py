# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from garage_management.permissions import assigned_doc_has_permission, assigned_doc_query_conditions


class RepairJob(Document):
	def before_insert(self):
		if not self.assigned_to:
			self.assigned_to = frappe.session.user
		if self.service_request and not self.job_type:
			self.job_type = frappe.db.get_value("Service Request", self.service_request, "job_type")

	def validate(self):
		self.sync_fetched_fields()
		self.enforce_photo_stages()
		self.validate_service_request_status()
		self.validate_status_transition()
		if self.inspection:
			parent = frappe.db.get_value("Inspection", self.inspection, "service_request")
			if parent and parent != self.service_request:
				frappe.throw(_("Selected Inspection does not belong to this Service Request"))

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
			["customer", "customer_name", "company"],
			as_dict=True,
		)
		if values:
			self.customer = values.customer
			self.customer_name = values.customer_name
			self.company = values.company

	def enforce_photo_stages(self):
		"""Ensure all photos in Repair Job are tagged as Completion stage."""
		for row in self.photos or []:
			row.stage = "Completion"

	def validate_service_request_status(self):
		"""Prevent creating/editing repair job on a cancelled Service Request."""
		if not self.service_request:
			return
		sr_status = frappe.db.get_value("Service Request", self.service_request, "status")
		if sr_status == "Cancelled":
			frappe.throw(_("Cannot create/update a Repair Job for a Cancelled Service Request"))

	def validate_status_transition(self):
		"""Guard against invalid backwards status transitions."""
		if self.is_new():
			return
		old_status = frappe.db.get_value("Repair Job", self.name, "status")
		forward_order = ["Draft", "In Progress", "Testing", "Completed", "Cancelled"]
		if old_status and self.status:
			old_idx = forward_order.index(old_status) if old_status in forward_order else -1
			new_idx = forward_order.index(self.status) if self.status in forward_order else -1
			# Allow going to Cancelled from any state, block other backwards moves
			if self.status != "Cancelled" and new_idx < old_idx:
				frappe.throw(
					_("Cannot move Repair Job status from {0} back to {1}").format(old_status, self.status)
				)

	def bump_parent_status(self):
		if self.flags.skip_request_sync:
			return
		if not self.service_request or self.status == "Cancelled":
			return
		parent_status = frappe.db.get_value("Service Request", self.service_request, "status")
		if self.status in ("In Progress", "Testing") and parent_status == "In Progress":
			if self.status == "Testing":
				others = frappe.get_all(
					"Repair Job",
					filters={
						"service_request": self.service_request,
						"name": ["!=", self.name],
						"status": ["not in", ["Completed", "Cancelled", "Testing"]],
					},
					limit=1,
				)
				if not others:
					frappe.db.set_value("Service Request", self.service_request, "status", "Testing")
		elif self.status == "Completed" and parent_status in ("In Progress", "Testing"):
			open_jobs = frappe.get_all(
				"Repair Job",
				filters={
					"service_request": self.service_request,
					"name": ["!=", self.name],
					"status": ["not in", ["Completed", "Cancelled"]],
				},
				limit=1,
			)
			if not open_jobs:
				frappe.db.set_value("Service Request", self.service_request, "status", "Testing")

	@frappe.whitelist()
	def load_job_type_defaults(self):
		if not self.job_type:
			frappe.throw(_("Select a Job Type first"))

		job_type = frappe.get_doc("Job Type", self.job_type)
		self.set("qc_items", [])
		for row in job_type.qc_items:
			self.append("qc_items", {"test_name": row.test_name, "result": "Pending"})
		return self

	@frappe.whitelist()
	def start_work(self):
		self.db_set("status", "In Progress", update_modified=True)
		self.bump_parent_status()
		frappe.msgprint(_("Repair Job marked as In Progress"), indicator="green", alert=True)
		return self.name

	@frappe.whitelist()
	def send_to_testing(self):
		self.db_set("status", "Testing", update_modified=True)
		self.bump_parent_status()
		frappe.msgprint(_("Repair Job sent for Testing"), indicator="green", alert=True)
		return self.name

	@frappe.whitelist()
	def mark_completed(self):
		self.db_set("status", "Completed", update_modified=True)
		self.bump_parent_status()
		frappe.msgprint(_("Repair Job marked as Completed"), indicator="green", alert=True)
		return self.name


def get_permission_query_conditions(user=None):
	return assigned_doc_query_conditions("Repair Job", user)


def has_permission(doc, ptype=None, user=None):
	return assigned_doc_has_permission(doc, user)
