# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from garage_management.permissions import assigned_doc_has_permission, assigned_doc_query_conditions

class RepairJob(Document):
	def onload(self):
		from garage_management.garage_management.doctype.service_job_settings.service_job_settings import (
			get_default_letter_head,
		)

		lh = get_default_letter_head()
		if lh:
			self.set_onload("default_letter_head", lh)
			self.letter_head = lh

	def before_print(self, settings=None):
		from garage_management.garage_management.doctype.service_job_settings.service_job_settings import (
			get_default_letter_head,
		)

		lh = get_default_letter_head()
		if lh:
			self.letter_head = lh

	def before_insert(self):
		if not self.assigned_to:
			self.assigned_to = frappe.session.user
		if self.service_request and not self.job_type:
			self.job_type = frappe.db.get_value("Service Request", self.service_request, "job_type")

	def validate(self):
		self.sync_fetched_fields()
		self.enforce_photo_stages()
		self.calculate_spare_parts_totals()
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

	def calculate_spare_parts_totals(self):
		total = 0.0
		default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse")
		price_list = frappe.db.get_single_value("Service Job Settings", "default_price_list")

		for row in self.spare_parts or []:
			if row.item_code:
				if not row.item_name or not row.uom:
					details = frappe.db.get_value(
						"Item",
						row.item_code,
						["item_name", "stock_uom", "description", "standard_rate"],
						as_dict=True,
					)
					if details:
						row.item_name = row.item_name or details.item_name
						row.uom = row.uom or details.stock_uom
						row.description = row.description or details.description
						if not flt(row.rate):
							row.rate = details.standard_rate or 0

				if not flt(row.rate) and price_list:
					pl_rate = frappe.db.get_value(
						"Item Price",
						{"item_code": row.item_code, "price_list": price_list, "selling": 1},
						"price_list_rate",
					)
					if pl_rate:
						row.rate = pl_rate

				if not row.warehouse and default_wh:
					is_stock = cint(frappe.db.get_value("Item", row.item_code, "is_stock_item"))
					if is_stock:
						row.warehouse = default_wh

			row.amount = flt(row.qty or 1) * flt(row.rate or 0)
			total += flt(row.amount)

		self.total_spare_parts_amount = total

	@frappe.whitelist()
	def sync_spare_parts_to_service_request(self):
		if not self.service_request:
			frappe.throw(_("No Service Request linked to this Repair Job"))

		req = frappe.get_doc("Service Request", self.service_request)
		existing_items = {row.item_code for row in req.billing_items if row.item_code}
		added = 0
		default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse")

		for row in self.spare_parts or []:
			if not row.item_code or row.item_code in existing_items:
				continue

			item_details = frappe.db.get_value(
				"Item",
				row.item_code,
				["item_name", "description", "is_stock_item"],
				as_dict=True,
			)
			if not item_details:
				continue

			req.append(
				"billing_items",
				{
					"item_code": row.item_code,
					"item_name": row.item_name or item_details.item_name,
					"description": row.description or item_details.description,
					"qty": row.qty or 1,
					"rate": row.rate or 0,
					"amount": row.amount or (flt(row.qty or 1) * flt(row.rate or 0)),
					"warehouse": row.warehouse or (default_wh if item_details.is_stock_item else None),
					"is_stock_item": item_details.is_stock_item,
				},
			)
			existing_items.add(row.item_code)
			added += 1

		if added > 0:
			req.save(ignore_permissions=True)
			frappe.msgprint(
				_("{0} spare part(s) synced to Service Request {1} billing items").format(added, self.service_request),
				indicator="green",
				alert=True,
			)
		else:
			frappe.msgprint(
				_("No new spare parts to sync (items already present in billing items)"),
				indicator="orange",
				alert=True,
			)

		return added

	@frappe.whitelist()
	def get_inspection_details(self, inspection_name=None):
		# Collect all inspections for this Service Request and/or Repair Job
		all_inspections = []
		seen_names = set()

		if self.service_request:
			insps = frappe.get_all(
				"Inspection",
				filters={"service_request": self.service_request, "status": ["!=", "Cancelled"]},
				fields=["name", "status", "assigned_to", "creation"],
				order_by="creation desc",
			)
			for i in insps:
				all_inspections.append(i)
				seen_names.add(i.name)

		if self.inspection and self.inspection not in seen_names:
			if frappe.db.exists("Inspection", self.inspection):
				val = frappe.db.get_value(
					"Inspection",
					self.inspection,
					["name", "status", "assigned_to", "creation"],
					as_dict=True,
				)
				if val:
					all_inspections.insert(0, val)
					seen_names.add(val.name)

		if not all_inspections and not inspection_name:
			return None

		# Enrich all_inspections with item counts and linked status
		enriched_inspections = []
		for i in all_inspections:
			findings_count = frappe.db.count("Inspection Finding Item", {"parent": i.name, "parentfield": "findings"})
			parts_count = frappe.db.count("Inspection Part Result", {"parent": i.name, "parentfield": "part_results"})
			key_items_count = frappe.db.count("Inspection Key Replacement Item", {"parent": i.name, "parentfield": "key_replacement_items"})
			enriched_inspections.append({
				"name": i.name,
				"status": i.status,
				"assigned_to": i.assigned_to,
				"creation": str(i.creation),
				"is_linked": (i.name == self.inspection),
				"findings_count": findings_count,
				"parts_count": parts_count,
				"key_items_count": key_items_count,
			})

		# Determine target inspection
		target_insp_name = inspection_name
		if not target_insp_name:
			if self.inspection and frappe.db.exists("Inspection", self.inspection):
				target_insp_name = self.inspection
			elif all_inspections:
				target_insp_name = all_inspections[0].name

		if not target_insp_name or not frappe.db.exists("Inspection", target_insp_name):
			return {"all_inspections": enriched_inspections, "selected_inspection": None}

		insp = frappe.get_doc("Inspection", target_insp_name)

		findings = []
		for f in (insp.findings or []):
			finding_id = getattr(f, "inspection_finding", None) or getattr(f, "finding_name", None)
			if not finding_id:
				continue
			desc = frappe.db.get_value("Inspection Finding", finding_id, "description") or ""
			findings.append({
				"finding_name": finding_id,
				"description": desc,
			})

		res = {
			"name": insp.name,
			"status": insp.status,
			"assigned_to": insp.assigned_to,
			"creation": str(insp.creation),
			"inspection_notes": insp.inspection_notes,
			"recommended_work": insp.recommended_work,
			"findings": findings,
			"part_results": [
				{
					"repair_asset": getattr(p, "repair_asset", None),
					"serial_number": getattr(p, "serial_number", None),
					"make_type": getattr(p, "make_type", None),
					"part_no": getattr(p, "part_no", None),
					"condition": getattr(p, "condition", None),
					"test_bench_results": getattr(p, "test_bench_results", None),
					"damaged_part_photo": getattr(p, "damaged_part_photo", None),
				}
				for p in (insp.part_results or [])
			],
			"key_replacement_items": [
				{
					"item_code": getattr(k, "item_code", None),
					"item_name": frappe.db.get_value("Item", getattr(k, "item_code", None), "item_name") or getattr(k, "item_code", None),
				}
				for k in (insp.key_replacement_items or [])
				if getattr(k, "item_code", None)
			],
			"photos": [
				{
					"image": getattr(ph, "image", None),
					"stage": getattr(ph, "stage", None),
					"notes": getattr(ph, "notes", None),
				}
				for ph in (insp.photos or [])
				if getattr(ph, "image", None)
			],
			"is_linked": (insp.name == self.inspection),
			"all_inspections": enriched_inspections,
			"total_inspections": len(enriched_inspections),
		}
		return res


def get_permission_query_conditions(user=None):
	return assigned_doc_query_conditions("Repair Job", user)


def has_permission(doc, ptype=None, user=None):
	return assigned_doc_has_permission(doc, user)
