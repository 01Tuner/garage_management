# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ROLES = ("Garage Front Desk", "Garage Technician", "Garage Manager")


def after_install():
	create_roles()
	setup_custom_fields()
	create_item_groups()
	ensure_settings()
	create_kanban_board()
	create_workspace_artifacts()
	from garage_management.patches.v1_0.seed_garage_masters import seed_part_types
	from garage_management.patches.v1_0.seed_inspection_findings import seed_inspection_findings

	seed_part_types()
	seed_inspection_findings()
	frappe.clear_cache()


def after_migrate():
	create_roles()
	setup_custom_fields()
	create_item_groups()
	ensure_settings()
	create_kanban_board()
	create_workspace_artifacts()
	from garage_management.patches.v1_0.seed_garage_masters import seed_part_types
	from garage_management.patches.v1_0.seed_inspection_findings import seed_inspection_findings
	from garage_management.patches.v1_0.split_service_job_to_request import _remap_commercial_links

	seed_part_types()
	seed_inspection_findings()
	_remap_commercial_links()


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def setup_custom_fields():
	custom_fields = {
		"Quotation": [
			{
				"fieldname": "service_request",
				"label": "Service Request",
				"fieldtype": "Link",
				"options": "Service Request",
				"insert_after": "order_type",
				"print_hide": 1,
			}
		],
		"Sales Order": [
			{
				"fieldname": "service_request",
				"label": "Service Request",
				"fieldtype": "Link",
				"options": "Service Request",
				"insert_after": "order_type",
				"print_hide": 1,
			}
		],
		"Sales Invoice": [
			{
				"fieldname": "service_request",
				"label": "Service Request",
				"fieldtype": "Link",
				"options": "Service Request",
				"insert_after": "customer",
				"print_hide": 1,
			}
		],
	}
	create_custom_fields(custom_fields, ignore_validate=True)
	_hide_legacy_service_job_fields()


def _hide_legacy_service_job_fields():
	for dt in ("Quotation", "Sales Order", "Sales Invoice"):
		name = f"{dt}-service_job"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value(
				"Custom Field",
				name,
				{"hidden": 1, "read_only": 1, "print_hide": 1},
				update_modified=False,
			)


def create_item_groups():
	parents = [
		{"doctype": "Item Group", "item_group_name": "Garage", "parent_item_group": "All Item Groups", "is_group": 1},
		{
			"doctype": "Item Group",
			"item_group_name": "Labour / Services",
			"parent_item_group": "Garage",
			"is_group": 0,
		},
		{
			"doctype": "Item Group",
			"item_group_name": "Spare Parts",
			"parent_item_group": "Garage",
			"is_group": 0,
		},
		{
			"doctype": "Item Group",
			"item_group_name": "Key Replacement Items",
			"parent_item_group": "Garage",
			"is_group": 0,
		},
	]
	for row in parents:
		if not frappe.db.exists("Item Group", row["item_group_name"]):
			try:
				frappe.get_doc(row).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(title=f"Garage Item Group {row['item_group_name']}")


def ensure_settings():
	if not frappe.db.exists("DocType", "Service Job Settings"):
		return
	doc = frappe.get_single("Service Job Settings")
	if not doc.company:
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		if company:
			doc.company = company
			doc.save(ignore_permissions=True)


def create_kanban_board():
	if not frappe.db.exists("DocType", "Service Request"):
		return

	_upsert_kanban(
		"Service Request by Status",
		"Service Request",
		[
			"Received",
			"Inspecting",
			"Quoted",
			"Awaiting Approval",
			"In Progress",
			"Testing",
			"Completed",
			"Invoiced",
			"Delivered",
			"On Hold",
		],
		["priority", "job_type", "complaint", "billing_total", "quotation", "sales_order", "sales_invoice", "mobile_no"],
	)
	_upsert_kanban(
		"Inspection by Status",
		"Inspection",
		["Draft", "In Progress", "Completed"],
		["assigned_to", "service_request", "customer_name"],
	)
	_upsert_kanban(
		"Repair Job by Status",
		"Repair Job",
		["Draft", "In Progress", "Testing", "Completed"],
		["assigned_to", "service_request", "job_type", "customer_name"],
	)

	if frappe.db.exists("Kanban Board", "Service Job by Status"):
		frappe.db.set_value("Kanban Board", "Service Job by Status", "private", 1, update_modified=False)


def _upsert_kanban(name, doctype, columns, fields):
	import json

	fields_json = json.dumps(fields)
	if frappe.db.exists("Kanban Board", name):
		board = frappe.get_doc("Kanban Board", name)
		board.reference_doctype = doctype
		board.field_name = "status"
		board.private = 0
		board.fields = fields_json
		board.show_labels = 1
		board.set("columns", [])
		for col in columns:
			board.append("columns", {"column_name": col, "status": "Active"})
		board.save(ignore_permissions=True)
		return

	board = frappe.get_doc(
		{
			"doctype": "Kanban Board",
			"kanban_board_name": name,
			"reference_doctype": doctype,
			"field_name": "status",
			"private": 0,
			"fields": fields_json,
			"show_labels": 1,
			"columns": [{"column_name": c, "status": "Active"} for c in columns],
		}
	)
	board.insert(ignore_permissions=True)


def create_workspace_artifacts():
	"""Number cards, dashboard charts, and Garage workspace."""
	if not frappe.db.exists("DocType", "Service Request"):
		return

	_ensure_number_cards()
	_ensure_dashboard_charts()
	_ensure_workspace()


def _ensure_number_cards():
	cards = [
		_count_card("Garage Jobs Open", "Service Request", '[["Service Request","status","not in",["Completed","Invoiced","Delivered","Cancelled"],false]]', "#2563eb"),
		_count_card("Garage Received", "Service Request", '[["Service Request","status","=","Received"]]', "#0ea5e9"),
		_count_card("Garage Inspecting", "Service Request", '[["Service Request","status","=","Inspecting"]]', "#f97316"),
		_count_card("Garage Quoted", "Service Request", '[["Service Request","status","=","Quoted"]]', "#eab308"),
		_count_card("Garage Awaiting Approval", "Service Request", '[["Service Request","status","=","Awaiting Approval"]]', "#a855f7"),
		_count_card("Garage In Progress", "Service Request", '[["Service Request","status","=","In Progress"]]', "#06b6d4"),
		_count_card("Garage On Hold", "Service Request", '[["Service Request","status","=","On Hold"]]', "#fb7185"),
		_count_card(
			"Garage Completed Today",
			"Service Request",
			'[["Service Request","status","in",["Completed","Invoiced","Delivered"]],["Service Request","modified","Timespan","today"]]',
			"#22c55e",
		),
		_count_card(
			"Garage Inspections Open",
			"Inspection",
			'[["Inspection","status","in",["Draft","In Progress"]]]',
			"#f59e0b",
		),
		_count_card(
			"Garage Repairs Open",
			"Repair Job",
			'[["Repair Job","status","in",["Draft","In Progress","Testing"]]]',
			"#14b8a6",
		),
		{
			"doctype": "Number Card",
			"label": "Garage Billing Pipeline",
			"type": "Document Type",
			"document_type": "Service Request",
			"function": "Sum",
			"aggregate_function_based_on": "billing_total",
			"filters_json": '[["Service Request","status","not in",["Cancelled"],false]]',
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Weekly",
			"color": "#7c3aed",
		},
		{
			"doctype": "Number Card",
			"label": "Garage Revenue MTD",
			"type": "Document Type",
			"document_type": "Sales Invoice",
			"function": "Sum",
			"aggregate_function_based_on": "grand_total",
			"filters_json": '[["Sales Invoice","service_request","is","set"],["Sales Invoice","docstatus","=",1],["Sales Invoice","posting_date","Timespan","this month"]]',
			"is_public": 1,
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly",
			"color": "#16a34a",
		},
		_count_card(
			"Garage Invoices (MTD)",
			"Sales Invoice",
			'[["Sales Invoice","service_request","is","set"],["Sales Invoice","docstatus","=",1],["Sales Invoice","posting_date","Timespan","this month"]]',
			"#059669",
		),
		_count_card("Garage Cancelled", "Service Request", '[["Service Request","status","=","Cancelled"]]', "#ef4444"),
	]
	for card in cards:
		_upsert("Number Card", card["label"], card)


def _count_card(label, doctype, filters_json, color):
	return {
		"doctype": "Number Card",
		"label": label,
		"type": "Document Type",
		"document_type": doctype,
		"function": "Count",
		"filters_json": filters_json,
		"is_public": 1,
		"show_percentage_stats": 1,
		"stats_time_interval": "Weekly",
		"color": color,
	}


def _ensure_dashboard_charts():
	charts = [
		{
			"chart_name": "Garage Jobs by Status",
			"chart_type": "Group By",
			"document_type": "Service Request",
			"group_by_type": "Count",
			"group_by_based_on": "status",
			"is_public": 1,
			"type": "Donut",
			"timeseries": 0,
			"filters_json": "[]",
			"color": "#2563eb",
		},
		{
			"chart_name": "Garage Jobs by Priority",
			"chart_type": "Group By",
			"document_type": "Service Request",
			"group_by_type": "Count",
			"group_by_based_on": "priority",
			"is_public": 1,
			"type": "Pie",
			"timeseries": 0,
			"filters_json": '[["Service Request","status","not in",["Cancelled"]]]',
			"color": "#f97316",
		},
		{
			"chart_name": "Garage Jobs by Type",
			"chart_type": "Group By",
			"document_type": "Service Request",
			"group_by_type": "Count",
			"group_by_based_on": "job_type",
			"is_public": 1,
			"type": "Donut",
			"timeseries": 0,
			"filters_json": "[]",
			"color": "#0ea5e9",
		},
		{
			"chart_name": "Garage Jobs This Week",
			"chart_type": "Count",
			"document_type": "Service Request",
			"based_on": "received_date",
			"time_interval": "Daily",
			"timespan": "Last Week",
			"timeseries": 1,
			"is_public": 1,
			"type": "Bar",
			"filters_json": "[]",
			"color": "#2563eb",
		},
		{
			"chart_name": "Garage Inspections by Status",
			"chart_type": "Group By",
			"document_type": "Inspection",
			"group_by_type": "Count",
			"group_by_based_on": "status",
			"is_public": 1,
			"type": "Donut",
			"timeseries": 0,
			"filters_json": "[]",
			"color": "#f59e0b",
		},
		{
			"chart_name": "Garage Repair Jobs by Status",
			"chart_type": "Group By",
			"document_type": "Repair Job",
			"group_by_type": "Count",
			"group_by_based_on": "status",
			"is_public": 1,
			"type": "Donut",
			"timeseries": 0,
			"filters_json": "[]",
			"color": "#14b8a6",
		},
		{
			"chart_name": "Garage Invoice Revenue MTD",
			"chart_type": "Sum",
			"document_type": "Sales Invoice",
			"based_on": "posting_date",
			"value_based_on": "grand_total",
			"time_interval": "Daily",
			"timespan": "Last Month",
			"timeseries": 1,
			"is_public": 1,
			"type": "Bar",
			"filters_json": '[["Sales Invoice","service_request","is","set"],["Sales Invoice","docstatus","=",1]]',
			"color": "#16a34a",
		},
		{
			"chart_name": "Garage Billing by Status",
			"chart_type": "Group By",
			"document_type": "Service Request",
			"group_by_type": "Sum",
			"group_by_based_on": "status",
			"aggregate_function_based_on": "billing_total",
			"is_public": 1,
			"type": "Bar",
			"timeseries": 0,
			"filters_json": '[["Service Request","status","not in",["Cancelled"]]]',
			"color": "#7c3aed",
		},
	]
	for chart in charts:
		_upsert("Dashboard Chart", chart["chart_name"], {**chart, "doctype": "Dashboard Chart"})


def _ensure_workspace():
	import json

	name = "Garage"
	content = [
		{"id": "qa_header", "type": "header", "data": {"text": "<span class=\"h4\">Quick Actions</span>", "col": 12}},
		{"id": "sc_new_sr", "type": "shortcut", "data": {"shortcut_name": "New Service Request", "col": 3}},
		{"id": "sc_kanban", "type": "shortcut", "data": {"shortcut_name": "Request Kanban", "col": 3}},
		{"id": "sc_insp", "type": "shortcut", "data": {"shortcut_name": "Inspections", "col": 3}},
		{"id": "sc_repair", "type": "shortcut", "data": {"shortcut_name": "Repair Jobs", "col": 3}},
		{"id": "sc_customer", "type": "shortcut", "data": {"shortcut_name": "New Customer", "col": 3}},
		{"id": "sc_quote", "type": "shortcut", "data": {"shortcut_name": "Quotations", "col": 3}},
		{"id": "sc_invoice", "type": "shortcut", "data": {"shortcut_name": "Sales Invoices", "col": 3}},
		{"id": "sc_item", "type": "shortcut", "data": {"shortcut_name": "Items", "col": 3}},
		{"id": "kpi_header", "type": "header", "data": {"text": "<span class=\"h4\">Workshop Pulse</span>", "col": 12}},
		{"id": "nc_open", "type": "number_card", "data": {"number_card_name": "Garage Jobs Open", "col": 3}},
		{"id": "nc_recv", "type": "number_card", "data": {"number_card_name": "Garage Received", "col": 3}},
		{"id": "nc_insp", "type": "number_card", "data": {"number_card_name": "Garage Inspecting", "col": 3}},
		{"id": "nc_quoted", "type": "number_card", "data": {"number_card_name": "Garage Quoted", "col": 3}},
		{"id": "nc_await", "type": "number_card", "data": {"number_card_name": "Garage Awaiting Approval", "col": 3}},
		{"id": "nc_ip", "type": "number_card", "data": {"number_card_name": "Garage In Progress", "col": 3}},
		{"id": "nc_hold", "type": "number_card", "data": {"number_card_name": "Garage On Hold", "col": 3}},
		{"id": "nc_done", "type": "number_card", "data": {"number_card_name": "Garage Completed Today", "col": 3}},
		{"id": "work_header", "type": "header", "data": {"text": "<span class=\"h4\">Floor Load</span>", "col": 12}},
		{"id": "nc_insp_open", "type": "number_card", "data": {"number_card_name": "Garage Inspections Open", "col": 3}},
		{"id": "nc_rj_open", "type": "number_card", "data": {"number_card_name": "Garage Repairs Open", "col": 3}},
		{"id": "nc_bill", "type": "number_card", "data": {"number_card_name": "Garage Billing Pipeline", "col": 3}},
		{"id": "nc_rev", "type": "number_card", "data": {"number_card_name": "Garage Revenue MTD", "col": 3}},
		{"id": "money_header", "type": "header", "data": {"text": "<span class=\"h4\">Commercial</span>", "col": 12}},
		{"id": "nc_inv", "type": "number_card", "data": {"number_card_name": "Garage Invoices (MTD)", "col": 3}},
		{"id": "nc_can", "type": "number_card", "data": {"number_card_name": "Garage Cancelled", "col": 3}},
		{"id": "chart_header", "type": "header", "data": {"text": "<span class=\"h4\">Pipeline</span>", "col": 12}},
		{"id": "ch_status", "type": "chart", "data": {"chart_name": "Garage Jobs by Status", "col": 4}},
		{"id": "ch_prio", "type": "chart", "data": {"chart_name": "Garage Jobs by Priority", "col": 4}},
		{"id": "ch_type", "type": "chart", "data": {"chart_name": "Garage Jobs by Type", "col": 4}},
		{"id": "act_header", "type": "header", "data": {"text": "<span class=\"h4\">Activity</span>", "col": 12}},
		{"id": "ch_week", "type": "chart", "data": {"chart_name": "Garage Jobs This Week", "col": 4}},
		{"id": "ch_insp", "type": "chart", "data": {"chart_name": "Garage Inspections by Status", "col": 4}},
		{"id": "ch_rj", "type": "chart", "data": {"chart_name": "Garage Repair Jobs by Status", "col": 4}},
		{"id": "rev_header", "type": "header", "data": {"text": "<span class=\"h4\">Revenue</span>", "col": 12}},
		{"id": "ch_rev", "type": "chart", "data": {"chart_name": "Garage Invoice Revenue MTD", "col": 6}},
		{"id": "ch_bill", "type": "chart", "data": {"chart_name": "Garage Billing by Status", "col": 6}},
		{"id": "links_header", "type": "header", "data": {"text": "<span class=\"h4\">Workshop Links</span>", "col": 12}},
		{"id": "card_workshop", "type": "card", "data": {"card_name": "Workshop", "col": 3}},
		{"id": "card_commercial", "type": "card", "data": {"card_name": "Commercial", "col": 3}},
		{"id": "card_reports", "type": "card", "data": {"card_name": "Reports", "col": 3}},
		{"id": "card_masters", "type": "card", "data": {"card_name": "Masters & Setup", "col": 3}},
	]

	open_filter = '[["Service Request","status","not in",["Completed","Invoiced","Delivered","Cancelled"]]]'
	insp_open = '[["Inspection","status","in",["Draft","In Progress"]]]'
	rj_open = '[["Repair Job","status","in",["Draft","In Progress","Testing"]]]'
	quote_open = '[["Quotation","docstatus","=",1],["Quotation","status","not in",["Ordered","Lost","Cancelled"]]]'

	shortcuts = [
		{
			"label": "New Service Request",
			"link_to": "Service Request",
			"type": "DocType",
			"doc_view": "New",
			"icon": "add",
			"color": "#2563eb",
		},
		{
			"label": "Request Kanban",
			"link_to": "Service Request",
			"type": "DocType",
			"doc_view": "Kanban",
			"kanban_board": "Service Request by Status",
			"icon": "kanban",
			"color": "#0ea5e9",
			"stats_filter": open_filter,
			"format": "{} Open",
		},
		{
			"label": "Inspections",
			"link_to": "Inspection",
			"type": "DocType",
			"doc_view": "Kanban",
			"kanban_board": "Inspection by Status",
			"icon": "quality",
			"color": "#f59e0b",
			"stats_filter": insp_open,
			"format": "{} Open",
		},
		{
			"label": "Repair Jobs",
			"link_to": "Repair Job",
			"type": "DocType",
			"doc_view": "Kanban",
			"kanban_board": "Repair Job by Status",
			"icon": "tool",
			"color": "#14b8a6",
			"stats_filter": rj_open,
			"format": "{} Open",
		},
		{"label": "New Customer", "link_to": "Customer", "type": "DocType", "doc_view": "New", "icon": "users", "color": "#6366f1"},
		{
			"label": "Quotations",
			"link_to": "Quotation",
			"type": "DocType",
			"icon": "file",
			"color": "#eab308",
			"stats_filter": quote_open,
			"format": "{} Open",
		},
		{"label": "Sales Invoices", "link_to": "Sales Invoice", "type": "DocType", "icon": "money-coins-1", "color": "#16a34a"},
		{"label": "Items", "link_to": "Item", "type": "DocType", "icon": "stock", "color": "#64748b"},
	]

	links = [
		{"label": "Workshop", "type": "Card Break", "link_count": 5, "icon": "tool"},
		{"label": "Service Request", "link_type": "DocType", "link_to": "Service Request", "type": "Link", "onboard": 1},
		{"label": "Inspection", "link_type": "DocType", "link_to": "Inspection", "type": "Link"},
		{"label": "Repair Job", "link_type": "DocType", "link_to": "Repair Job", "type": "Link"},
		{"label": "Customer", "link_type": "DocType", "link_to": "Customer", "type": "Link"},
		{"label": "Contact", "link_type": "DocType", "link_to": "Contact", "type": "Link"},
		{"label": "Commercial", "type": "Card Break", "link_count": 4, "icon": "file"},
		{"label": "Quotation", "link_type": "DocType", "link_to": "Quotation", "type": "Link"},
		{"label": "Sales Order", "link_type": "DocType", "link_to": "Sales Order", "type": "Link"},
		{"label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice", "type": "Link"},
		{"label": "Payment Entry", "link_type": "DocType", "link_to": "Payment Entry", "type": "Link"},
		{"label": "Reports", "type": "Card Break", "link_count": 6, "icon": "table"},
		{"label": "Garage Jobs In Progress", "link_type": "Report", "link_to": "Garage Jobs In Progress", "type": "Link", "is_query_report": 1},
		{"label": "Garage Completed Jobs", "link_type": "Report", "link_to": "Garage Completed Jobs", "type": "Link", "is_query_report": 1},
		{"label": "Garage Technician Performance", "link_type": "Report", "link_to": "Garage Technician Performance", "type": "Link", "is_query_report": 1},
		{"label": "Garage Repeat Repairs", "link_type": "Report", "link_to": "Garage Repeat Repairs", "type": "Link", "is_query_report": 1},
		{"label": "Garage Parts Sold", "link_type": "Report", "link_to": "Garage Parts Sold", "type": "Link", "is_query_report": 1},
		{"label": "Accounts Receivable", "link_type": "Report", "link_to": "Accounts Receivable", "type": "Link", "is_query_report": 1},
		{"label": "Masters & Setup", "type": "Card Break", "link_count": 6, "icon": "setting"},
		{"label": "Job Type", "link_type": "DocType", "link_to": "Job Type", "type": "Link"},
		{"label": "Part Type", "link_type": "DocType", "link_to": "Part Type", "type": "Link"},
		{"label": "Inspection Finding", "link_type": "DocType", "link_to": "Inspection Finding", "type": "Link"},
		{"label": "Item", "link_type": "DocType", "link_to": "Item", "type": "Link"},
		{"label": "Item Group", "link_type": "DocType", "link_to": "Item Group", "type": "Link"},
		{"label": "Service Job Settings", "link_type": "DocType", "link_to": "Service Job Settings", "type": "Link"},
	]

	number_cards = [
		{"number_card_name": "Garage Jobs Open", "label": "Open Jobs"},
		{"number_card_name": "Garage Received", "label": "Received"},
		{"number_card_name": "Garage Inspecting", "label": "Inspecting"},
		{"number_card_name": "Garage Quoted", "label": "Quoted"},
		{"number_card_name": "Garage Awaiting Approval", "label": "Awaiting Approval"},
		{"number_card_name": "Garage In Progress", "label": "In Progress"},
		{"number_card_name": "Garage On Hold", "label": "On Hold"},
		{"number_card_name": "Garage Completed Today", "label": "Done Today"},
		{"number_card_name": "Garage Inspections Open", "label": "Open Inspections"},
		{"number_card_name": "Garage Repairs Open", "label": "Open Repairs"},
		{"number_card_name": "Garage Billing Pipeline", "label": "Billing Pipeline"},
		{"number_card_name": "Garage Revenue MTD", "label": "Revenue MTD"},
		{"number_card_name": "Garage Invoices (MTD)", "label": "Invoices MTD"},
		{"number_card_name": "Garage Cancelled", "label": "Cancelled"},
	]

	charts = [
		{"chart_name": "Garage Jobs by Status", "label": "Jobs by Status"},
		{"chart_name": "Garage Jobs by Priority", "label": "Jobs by Priority"},
		{"chart_name": "Garage Jobs by Type", "label": "Jobs by Type"},
		{"chart_name": "Garage Jobs This Week", "label": "Received This Week"},
		{"chart_name": "Garage Inspections by Status", "label": "Inspections"},
		{"chart_name": "Garage Repair Jobs by Status", "label": "Repair Jobs"},
		{"chart_name": "Garage Invoice Revenue MTD", "label": "Invoice Revenue"},
		{"chart_name": "Garage Billing by Status", "label": "Billing by Status"},
	]

	payload = {
		"doctype": "Workspace",
		"name": name,
		"label": name,
		"title": name,
		"module": "Garage Management",
		"category": "Modules",
		"public": 1,
		"is_hidden": 0,
		"icon": "tool",
		"indicator_color": "orange",
		"content": json.dumps(content),
		"shortcuts": shortcuts,
		"links": links,
		"number_cards": number_cards,
		"charts": charts,
		"roles": [
			{"role": "Garage Front Desk"},
			{"role": "Garage Technician"},
			{"role": "Garage Manager"},
			{"role": "System Manager"},
			{"role": "Accounts User"},
		],
	}

	if frappe.db.exists("Workspace", name):
		doc = frappe.get_doc("Workspace", name)
		doc.update(payload)
		doc.set("shortcuts", [])
		doc.set("links", [])
		doc.set("number_cards", [])
		doc.set("charts", [])
		doc.set("roles", [])
		for s in shortcuts:
			doc.append("shortcuts", s)
		for link in links:
			doc.append("links", link)
		for nc in number_cards:
			doc.append("number_cards", nc)
		for ch in charts:
			doc.append("charts", ch)
		for role in payload["roles"]:
			doc.append("roles", role)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)


def _upsert(doctype, name, data):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		old_dt = doc.get("document_type")
		new_dt = data.get("document_type")
		old_chart_type = doc.get("chart_type")
		new_chart_type = data.get("chart_type")
		recreate = False
		if doctype in ("Dashboard Chart", "Number Card") and old_dt and new_dt and old_dt != new_dt:
			recreate = True
		if doctype == "Dashboard Chart" and old_chart_type and new_chart_type and old_chart_type != new_chart_type:
			recreate = True
		if recreate:
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
			frappe.get_doc(data).insert(ignore_permissions=True)
			return
		doc.update(data)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(data).insert(ignore_permissions=True)
