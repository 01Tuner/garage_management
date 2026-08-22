# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe

DEFAULT_FINDINGS = (
	"Routine replacement",
	"Normal wear and tear",
	"Fuel return leak",
	"Injector stuck from sitting too long",
	"Running pump dry",
	"Incorrect fuel injection timing",
	"Electrical or wiring problems",
	"Faulty fuel pump causing injector issues",
	"Air leaks in fuel system",
	"Over-tightened fittings",
	"Missing or reused washers or seals",
	"Parts fitted wrong or damaged during repair",
	"Control valve stuck",
	"Electrical connector damaged",
	"Solenoid coil failed",
	"Carbon build-up on nozzle",
	"Worn cam or rotor parts",
	"Weak or broken springs",
	"Nozzle tip worn or damaged",
	"Worn plunger or barrel",
	"Scored or scratched parts",
	"Parts worn out from use",
	"Fuel with wax or gel blockages",
	"Fuel mixed with oil",
	"Wrong type of fuel used",
	"Bad quality fuel",
	"Fuel filter clogged or failed",
	"Dirt or sand in fuel",
	"Rust inside parts",
	"Water in fuel",
)


def seed_inspection_findings():
	if not frappe.db.exists("DocType", "Inspection Finding"):
		return
	for name in DEFAULT_FINDINGS:
		if frappe.db.exists("Inspection Finding", name):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Inspection Finding",
					"finding_name": name,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Seed Inspection Finding {name}")


def execute():
	seed_inspection_findings()
