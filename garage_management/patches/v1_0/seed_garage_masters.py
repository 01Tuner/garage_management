# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe


DEFAULT_PART_TYPES = (
	{"part_type_name": "Injector", "description": "Diesel fuel injector"},
	{"part_type_name": "Fuel Pump", "description": "Diesel fuel pump"},
	{"part_type_name": "Other", "description": "Other diesel engine component"},
)


def seed_part_types():
	if not frappe.db.exists("DocType", "Part Type"):
		return
	for row in DEFAULT_PART_TYPES:
		if frappe.db.exists("Part Type", row["part_type_name"]):
			continue
		try:
			frappe.get_doc({"doctype": "Part Type", **row}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Seed Part Type {row['part_type_name']}")


def execute():
	"""Seed sample garage service/part items and job types if empty."""
	if not frappe.db.exists("Item Group", "Labour / Services"):
		return

	seed_part_types()

	samples = [
		{
			"item_code": "SRV-INJ-CLEAN",
			"item_name": "Injector Cleaning",
			"item_group": "Labour / Services",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": 150,
		},
		{
			"item_code": "SRV-PUMP-OH",
			"item_name": "Pump Overhaul",
			"item_group": "Labour / Services",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": 450,
		},
		{
			"item_code": "SRV-CALIB",
			"item_name": "Calibration",
			"item_group": "Labour / Services",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": 80,
		},
		{
			"item_code": "SRV-LABOUR-HR",
			"item_name": "Labour Hour",
			"item_group": "Labour / Services",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": 50,
		},
		{
			"item_code": "PRT-NOZZLE-KIT",
			"item_name": "Nozzle Kit",
			"item_group": "Spare Parts",
			"is_stock_item": 1,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"standard_rate": 220,
		},
		{
			"item_code": "PRT-SEAL-KIT",
			"item_name": "Seal Kit",
			"item_group": "Spare Parts",
			"is_stock_item": 1,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"standard_rate": 35,
		},
	]

	for row in samples:
		if frappe.db.exists("Item", row["item_code"]):
			continue
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Item",
					**row,
					"stock_uom": "Nos",
					"valuation_rate": row.get("standard_rate") or 1,
				}
			)
			doc.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Seed garage item {row['item_code']}")

	if not frappe.db.exists("Job Type", "Injector Cleaning"):
		try:
			jt = frappe.get_doc(
				{
					"doctype": "Job Type",
					"job_type_name": "Injector Cleaning",
					"description": "Standard injector clean and test",
					"billing_items": [
						{"item_code": "SRV-INJ-CLEAN", "qty": 1, "rate": 150},
						{"item_code": "SRV-CALIB", "qty": 1, "rate": 80},
					],
					"qc_items": [
						{"test_name": "Pressure Test"},
						{"test_name": "Leak Test"},
						{"test_name": "Calibration"},
					],
				}
			)
			jt.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Seed Job Type Injector Cleaning")

	if not frappe.db.exists("Job Type", "Pump Overhaul"):
		try:
			jt = frappe.get_doc(
				{
					"doctype": "Job Type",
					"job_type_name": "Pump Overhaul",
					"description": "Full fuel pump overhaul",
					"billing_items": [
						{"item_code": "SRV-PUMP-OH", "qty": 1, "rate": 450},
						{"item_code": "SRV-LABOUR-HR", "qty": 2, "rate": 50},
						{"item_code": "PRT-SEAL-KIT", "qty": 1, "rate": 35},
					],
					"qc_items": [
						{"test_name": "Pressure Test"},
						{"test_name": "Leak Test"},
					],
				}
			)
			jt.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Seed Job Type Pump Overhaul")
