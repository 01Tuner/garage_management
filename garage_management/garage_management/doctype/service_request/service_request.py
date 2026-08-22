# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, nowdate

from garage_management.permissions import is_garage_technician_only


class ServiceRequest(Document):
	def validate(self):
		self.set_defaults()
		self.calculate_billing_total()
		self.set_warranty_expiry()
		self.fetch_customer_mobile()
		if not self.components and not (
			self.flags.ignore_component_check or self.flags.ignore_missing_components
		):
			frappe.throw(_("Add at least one Customer Owned Part / Component"))

	def before_submit(self):
		if self.status == "Cancelled":
			frappe.throw(_("Cannot submit a Cancelled Service Request"))

	def on_update(self):
		self.send_status_email_if_needed()

	def on_update_after_submit(self):
		self.calculate_billing_total()
		self.set_warranty_expiry()
		self.send_status_email_if_needed()

	def set_defaults(self):
		if not self.company:
			settings = frappe.get_cached_doc("Service Job Settings")
			if settings.company:
				self.company = settings.company
			else:
				self.company = frappe.defaults.get_user_default("Company")

		if not self.warranty_days:
			settings = frappe.get_cached_doc("Service Job Settings")
			self.warranty_days = cint(settings.default_warranty_days) or 30

	def fetch_customer_mobile(self):
		if self.customer and not self.mobile_no:
			self.mobile_no = frappe.db.get_value("Customer", self.customer, "mobile_no")

	def calculate_billing_total(self):
		total = 0
		default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse")
		for row in self.billing_items:
			row.amount = flt(row.qty) * flt(row.rate)
			total += flt(row.amount)
			if row.item_code:
				row.is_stock_item = cint(frappe.db.get_value("Item", row.item_code, "is_stock_item"))
			if row.is_stock_item and not row.warehouse and default_wh:
				row.warehouse = default_wh
		self.billing_total = total

	def set_warranty_expiry(self):
		if self.status in ("Completed", "Invoiced", "Delivered") and self.warranty_days:
			self.warranty_expiry = add_days(getdate(nowdate()), cint(self.warranty_days))

	def send_status_email_if_needed(self):
		if self.flags.ignore_status_email:
			return

		settings = frappe.get_cached_doc("Service Job Settings")
		if not settings.notify_on_status_change:
			return

		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		recipients = []
		if settings.notification_recipients:
			recipients = [e.strip() for e in settings.notification_recipients.split(",") if e.strip()]

		if not recipients:
			assignees = frappe.get_all(
				"Inspection",
				filters={"service_request": self.name, "assigned_to": ["is", "set"]},
				pluck="assigned_to",
			) + frappe.get_all(
				"Repair Job",
				filters={"service_request": self.name, "assigned_to": ["is", "set"]},
				pluck="assigned_to",
			)
			for user in set(assignees):
				email = frappe.db.get_value("User", user, "email")
				if email:
					recipients.append(email)

		if not recipients:
			return

		try:
			frappe.sendmail(
				recipients=recipients,
				subject=_("Service Request {0}: {1}").format(self.name, self.status),
				message=_(
					"<p>Service Request <b>{0}</b> for <b>{1}</b> is now <b>{2}</b>.</p>"
					"<p>Complaint: {3}</p>"
				).format(
					self.name,
					self.customer_name or self.customer,
					self.status,
					self.complaint or "",
				),
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
		except Exception:
			frappe.log_error(title="Garage Service Request status email failed")

	@frappe.whitelist()
	def load_job_type_defaults(self):
		if not self.job_type:
			frappe.throw(_("Select a Job Type first"))

		job_type = frappe.get_doc("Job Type", self.job_type)
		self.set("billing_items", [])

		default_wh = frappe.db.get_single_value("Service Job Settings", "default_warehouse")
		price_list = frappe.db.get_single_value("Service Job Settings", "default_price_list")

		for row in job_type.billing_items:
			rate = row.rate
			if not rate and price_list:
				rate = frappe.db.get_value(
					"Item Price",
					{"item_code": row.item_code, "price_list": price_list, "selling": 1},
					"price_list_rate",
				)
			self.append(
				"billing_items",
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"description": row.description,
					"qty": row.qty or 1,
					"rate": rate or 0,
					"warehouse": row.warehouse or default_wh,
					"is_stock_item": row.is_stock_item,
				},
			)

		self.calculate_billing_total()
		return self

	@frappe.whitelist()
	def create_inspection(self, assigned_to=None):
		if self.is_new():
			frappe.throw(_("Save the Service Request first"))

		insp = frappe.new_doc("Inspection")
		insp.service_request = self.name
		insp.assigned_to = assigned_to or frappe.session.user
		insp.status = "Draft"
		for row in self.components:
			insp.append(
				"part_results",
				{
					"repair_asset": row.repair_asset,
					"serial_number": row.serial_number,
					"make_type": row.make_type,
					"part_no": row.part_no,
				},
			)
		insp.insert(ignore_permissions=True)
		if self.status == "Received":
			self.db_set("status", "Inspecting")
		return insp.name

	@frappe.whitelist()
	def create_repair_job(self, assigned_to=None, inspection=None):
		if self.is_new():
			frappe.throw(_("Save the Service Request first"))

		job = frappe.new_doc("Repair Job")
		job.service_request = self.name
		job.assigned_to = assigned_to or frappe.session.user
		job.inspection = inspection
		job.job_type = self.job_type
		job.status = "Draft"
		if job.job_type:
			job.load_job_type_defaults()
		job.insert(ignore_permissions=True)
		return job.name


@frappe.whitelist()
def create_inspection(service_request, assigned_to=None):
	req = frappe.get_doc("Service Request", service_request)
	return req.create_inspection(assigned_to=assigned_to)


@frappe.whitelist()
def create_repair_job(service_request, assigned_to=None, inspection=None):
	req = frappe.get_doc("Service Request", service_request)
	return req.create_repair_job(assigned_to=assigned_to, inspection=inspection)


@frappe.whitelist()
def create_repair_job_from_inspection(service_request, inspection=None, assigned_to=None):
	req = frappe.get_doc("Service Request", service_request)
	return req.create_repair_job(assigned_to=assigned_to, inspection=inspection)


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if not is_garage_technician_only(user):
		return None

	user_esc = frappe.db.escape(user)
	return f"""(`tabService Request`.name IN (
		SELECT service_request FROM `tabInspection` WHERE assigned_to = {user_esc}
		UNION
		SELECT service_request FROM `tabRepair Job` WHERE assigned_to = {user_esc}
	))"""


def has_permission(doc, ptype=None, user=None):
	if not user:
		user = frappe.session.user

	if not is_garage_technician_only(user):
		return True

	if frappe.db.exists("Inspection", {"service_request": doc.name, "assigned_to": user}):
		return True
	if frappe.db.exists("Repair Job", {"service_request": doc.name, "assigned_to": user}):
		return True
	return False
