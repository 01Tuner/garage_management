# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe

KEY_REPLACEMENT_ITEMS = [
	{
		"item_code": "PRT-NOZZLE-KIT",
		"item_name": "Nozzle Kit",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 220,
	},
	{
		"item_code": "PRT-SEAL-KIT",
		"item_name": "Seal Kit",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 35,
	},
	{
		"item_code": "PRT-CONTROL-VALVE",
		"item_name": "Control Valve",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 180,
	},
	{
		"item_code": "PRT-SOLENOID-VALVE",
		"item_name": "Solenoid Valve",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 120,
	},
	{
		"item_code": "PRT-PLUNGER-BARREL",
		"item_name": "Plunger & Barrel Set",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 260,
	},
	{
		"item_code": "PRT-GASKET-SET",
		"item_name": "Gasket & O-Ring Set",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 45,
	},
	{
		"item_code": "PRT-WASHER-SHIM",
		"item_name": "Washer & Shim Kit",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 25,
	},
	{
		"item_code": "PRT-FUEL-FILTER",
		"item_name": "Fuel Filter Element",
		"item_group": "Key Replacement Items",
		"is_stock_item": 1,
		"is_sales_item": 1,
		"is_purchase_item": 1,
		"standard_rate": 55,
	},
]


def ensure_key_replacement_item_group():
	if not frappe.db.exists("Item Group", "Garage"):
		try:
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": "Garage",
					"parent_item_group": "All Item Groups",
					"is_group": 1,
				}
			).insert(ignore_permissions=True)
		except Exception:
			pass

	if not frappe.db.exists("Item Group", "Key Replacement Items"):
		try:
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": "Key Replacement Items",
					"parent_item_group": "Garage" if frappe.db.exists("Item Group", "Garage") else "All Item Groups",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		except Exception:
			pass


def seed_key_replacement_items():
	ensure_key_replacement_item_group()

	for row in KEY_REPLACEMENT_ITEMS:
		if frappe.db.exists("Item", row["item_code"]):
			# Ensure existing item is placed in Key Replacement Items or Spare Parts
			current_group = frappe.db.get_value("Item", row["item_code"], "item_group")
			if current_group not in ("Key Replacement Items", "Spare Parts"):
				frappe.db.set_value("Item", row["item_code"], "item_group", "Key Replacement Items")
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
			frappe.log_error(title=f"Seed Key Replacement Item {row['item_code']}")


def execute():
	seed_key_replacement_items()
