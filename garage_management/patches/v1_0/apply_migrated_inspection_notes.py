# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Move parked old inspection findings text into inspection_notes."""
	if not frappe.db.exists("DocType", "Service Job"):
		return
	if not frappe.db.has_column("Service Job", "inspection_notes"):
		return

	marker = "\n<!--GARAGE_OLD_FINDINGS-->\n"
	jobs = frappe.get_all(
		"Service Job",
		filters=[["recommended_work", "like", f"%{marker.strip()}%"]],
		fields=["name", "recommended_work", "inspection_notes"],
	)
	for job in jobs:
		rw = job.recommended_work or ""
		if marker not in rw:
			# marker without leading newline variants
			if "<!--GARAGE_OLD_FINDINGS-->" not in rw:
				continue
			parts = rw.split("<!--GARAGE_OLD_FINDINGS-->", 1)
		else:
			parts = rw.split(marker, 1)

		recommended = parts[0].rstrip()
		old_findings = parts[1].strip() if len(parts) > 1 else ""
		notes = job.inspection_notes or ""
		if old_findings and old_findings not in notes:
			notes = f"{notes}\n{old_findings}".strip() if notes else old_findings
		frappe.db.set_value(
			"Service Job",
			job.name,
			{"recommended_work": recommended or None, "inspection_notes": notes or None},
			update_modified=False,
		)
