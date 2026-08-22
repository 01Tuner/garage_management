# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.modules.import_file import import_file_by_path


def execute():
	"""Import component child DocType, then move legacy component fields into rows.

	Runs in pre_model_sync so old Service Job columns still exist.
	"""
	app_path = frappe.get_app_path("garage_management")
	doctypes = [
		"part_type",
		"service_job_component",
		"inspection_finding",
		"service_job_inspection_finding",
	]
	for dt in doctypes:
		path = os.path.join(
			app_path,
			"garage_management",
			"doctype",
			dt,
			f"{dt}.json",
		)
		if os.path.exists(path):
			import_file_by_path(path, force=True, ignore_version=True)

	frappe.clear_cache()

	if not frappe.db.exists("DocType", "Service Job Component"):
		return
	if not frappe.db.exists("DocType", "Service Job"):
		return
	if not frappe.db.has_column("Service Job", "part_type"):
		return

	jobs = frappe.db.sql(
		"""
		SELECT name, part_type, part_number, serial_number, inspection_findings
		FROM `tabService Job`
		WHERE IFNULL(part_type, '') != '' OR IFNULL(serial_number, '') != '' OR IFNULL(part_number, '') != ''
			OR IFNULL(inspection_findings, '') != ''
		""",
		as_dict=True,
	)
	for job in jobs:
		if (job.part_type or job.serial_number or job.part_number) and not frappe.db.exists(
			"Service Job Component", {"parent": job.name}
		):
			repair_asset = job.part_type
			if repair_asset and not frappe.db.exists("Part Type", repair_asset):
				try:
					frappe.get_doc(
						{"doctype": "Part Type", "part_type_name": repair_asset}
					).insert(ignore_permissions=True)
				except Exception:
					repair_asset = None
			if not repair_asset:
				repair_asset = "Other"
				if not frappe.db.exists("Part Type", "Other"):
					frappe.get_doc({"doctype": "Part Type", "part_type_name": "Other"}).insert(
						ignore_permissions=True
					)
			child = frappe.get_doc(
				{
					"doctype": "Service Job Component",
					"parent": job.name,
					"parenttype": "Service Job",
					"parentfield": "components",
					"repair_asset": repair_asset,
					"serial_number": job.serial_number,
					"part_no": job.part_number,
				}
			)
			child.insert(ignore_permissions=True)

		# Park free-text findings into recommended_work so they are not lost when column is dropped.
		# Post sync, apply_migrated_inspection_notes moves the marker block into inspection_notes.
		if job.inspection_findings:
			marker = "\n<!--GARAGE_OLD_FINDINGS-->\n"
			current = frappe.db.get_value("Service Job", job.name, "recommended_work") or ""
			if marker not in current and "inspection_notes" not in (frappe.db.get_table_columns("Service Job") or []):
				frappe.db.set_value(
					"Service Job",
					job.name,
					"recommended_work",
					f"{current}{marker}{job.inspection_findings}",
					update_modified=False,
				)
