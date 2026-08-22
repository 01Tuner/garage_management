# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Technician", "fieldname": "technician", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Inspections", "fieldname": "inspections", "fieldtype": "Int", "width": 110},
		{"label": "Repair Jobs", "fieldname": "repair_jobs", "fieldtype": "Int", "width": 110},
		{"label": "Completed Repairs", "fieldname": "completed", "fieldtype": "Int", "width": 140},
		{"label": "In Progress", "fieldname": "in_progress", "fieldtype": "Int", "width": 110},
	]

	values = {}
	insp_date = ""
	rj_date = ""
	if filters.get("from_date"):
		insp_date += " AND DATE(creation) >= %(from_date)s"
		rj_date += " AND DATE(creation) >= %(from_date)s"
		values["from_date"] = getdate(filters.from_date)
	if filters.get("to_date"):
		insp_date += " AND DATE(creation) <= %(to_date)s"
		rj_date += " AND DATE(creation) <= %(to_date)s"
		values["to_date"] = getdate(filters.to_date)

	data = frappe.db.sql(
		f"""
		SELECT technician,
			SUM(inspections) AS inspections,
			SUM(repair_jobs) AS repair_jobs,
			SUM(completed) AS completed,
			SUM(in_progress) AS in_progress
		FROM (
			SELECT
				assigned_to AS technician,
				COUNT(*) AS inspections,
				0 AS repair_jobs,
				SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed,
				SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress
			FROM `tabInspection`
			WHERE IFNULL(assigned_to, '') != '' AND status != 'Cancelled' {insp_date}
			GROUP BY assigned_to
			UNION ALL
			SELECT
				assigned_to AS technician,
				0 AS inspections,
				COUNT(*) AS repair_jobs,
				SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed,
				SUM(CASE WHEN status IN ('In Progress','Testing') THEN 1 ELSE 0 END) AS in_progress
			FROM `tabRepair Job`
			WHERE IFNULL(assigned_to, '') != '' AND status != 'Cancelled' {rj_date}
			GROUP BY assigned_to
		) t
		GROUP BY technician
		ORDER BY (SUM(inspections) + SUM(repair_jobs)) DESC
		""",
		values,
		as_dict=True,
	)
	return columns, data
