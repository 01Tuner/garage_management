# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data, report_summary, chart = get_data(filters)
	return columns, data, None, chart, report_summary


def get_columns():
	return [
		{
			"label": _("Service Request"),
			"fieldname": "service_request",
			"fieldtype": "Link",
			"options": "Service Request",
			"width": 140,
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 95,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Vehicle / Equipment"),
			"fieldname": "components",
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Sales Invoices"),
			"fieldname": "sales_invoices",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Sales Revenue (Net)"),
			"fieldname": "sales_net",
			"fieldtype": "Currency",
			"width": 135,
		},
		{
			"label": _("Sales Total (Gross)"),
			"fieldname": "sales_grand",
			"fieldtype": "Currency",
			"width": 135,
		},
		{
			"label": _("Purchase Invoices"),
			"fieldname": "purchase_invoices",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Purchase Cost (Net)"),
			"fieldname": "purchase_net",
			"fieldtype": "Currency",
			"width": 135,
		},
		{
			"label": _("Purchase Total"),
			"fieldname": "purchase_grand",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Gross Profit"),
			"fieldname": "gross_profit",
			"fieldtype": "Currency",
			"width": 125,
		},
		{
			"label": _("Margin %"),
			"fieldname": "margin_pct",
			"fieldtype": "Percent",
			"width": 90,
		},
	]


def get_data(filters):
	conditions = ["sr.docstatus < 2"]
	values = {}

	if filters.get("company"):
		conditions.append("sr.company = %(company)s")
		values["company"] = filters["company"]

	if filters.get("customer"):
		conditions.append("sr.customer = %(customer)s")
		values["customer"] = filters["customer"]

	if filters.get("service_request"):
		conditions.append("sr.name = %(service_request)s")
		values["service_request"] = filters["service_request"]

	if filters.get("status"):
		conditions.append("sr.status = %(status)s")
		values["status"] = filters["status"]

	if filters.get("from_date"):
		conditions.append("DATE(COALESCE(sr.received_date, sr.creation)) >= %(from_date)s")
		values["from_date"] = getdate(filters["from_date"])

	if filters.get("to_date"):
		conditions.append("DATE(COALESCE(sr.received_date, sr.creation)) <= %(to_date)s")
		values["to_date"] = getdate(filters["to_date"])

	where_clause = " AND ".join(conditions)

	sr_list = frappe.db.sql(
		f"""
		SELECT
			sr.name,
			COALESCE(DATE(sr.received_date), DATE(sr.creation)) AS received_date,
			sr.customer,
			sr.customer_name,
			sr.status,
			sr.company,
			sr.sales_invoice,
			sr.billing_total
		FROM `tabService Request` sr
		WHERE {where_clause}
		ORDER BY sr.creation DESC
		""",
		values,
		as_dict=True,
	)

	if not sr_list:
		return [], [], None

	sr_names = [r.name for r in sr_list]

	# Fetch components (vehicles / repair assets)
	components_map = {}
	comps = frappe.get_all(
		"Service Request Component",
		filters={"parent": ["in", sr_names]},
		fields=["parent", "repair_asset", "serial_number"],
	)
	for c in comps:
		desc = f"{c.repair_asset or ''} ({c.serial_number})" if c.serial_number else (c.repair_asset or "")
		if desc:
			components_map.setdefault(c.parent, []).append(desc)

	# Fetch Sales Invoices linked to these Service Requests
	sales_invoices = frappe.db.sql(
		"""
		SELECT
			name,
			service_request,
			base_net_total,
			base_grand_total,
			docstatus
		FROM `tabSales Invoice`
		WHERE docstatus < 2
			AND (service_request IN %(sr_names)s OR name IN (
				SELECT sales_invoice FROM `tabService Request` WHERE name IN %(sr_names)s AND sales_invoice IS NOT NULL
			))
		""",
		{"sr_names": sr_names},
		as_dict=True,
	)

	sales_map = {}
	# Also map by direct link from Service Request
	sr_si_link = {r.name: r.sales_invoice for r in sr_list if r.sales_invoice}
	si_by_name = {si.name: si for si in sales_invoices}

	for si in sales_invoices:
		target_sr = si.service_request
		if not target_sr:
			# Find which SR links to this SI
			for s_name, linked_si in sr_si_link.items():
				if linked_si == si.name:
					target_sr = s_name
					break
		if target_sr:
			sales_map.setdefault(target_sr, []).append(si)

	# Fetch Purchase Invoices linked to these Service Requests (header level or item level)
	pi_rows = frappe.db.sql(
		"""
		SELECT DISTINCT
			pi.name,
			pi.service_request AS header_sr,
			pii.service_request AS item_sr,
			pi.base_net_total,
			pi.base_grand_total,
			pii.base_net_amount AS item_net,
			pii.base_amount AS item_gross
		FROM `tabPurchase Invoice` pi
		LEFT JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE pi.docstatus < 2
			AND (pi.service_request IN %(sr_names)s OR pii.service_request IN %(sr_names)s)
		""",
		{"sr_names": sr_names},
		as_dict=True,
	)

	# Group Purchase Invoices by Service Request
	purchases_map = {}
	seen_invoices = {}

	for pi in pi_rows:
		sr_id = pi.header_sr or pi.item_sr
		if not sr_id or sr_id not in sr_names:
			if pi.item_sr and pi.item_sr in sr_names:
				sr_id = pi.item_sr
			elif pi.header_sr and pi.header_sr in sr_names:
				sr_id = pi.header_sr
			else:
				continue

		if sr_id not in purchases_map:
			purchases_map[sr_id] = {
				"invoice_names": set(),
				"net_total": 0.0,
				"grand_total": 0.0,
			}

		inv_key = (sr_id, pi.name)
		if inv_key not in seen_invoices:
			seen_invoices[inv_key] = True
			purchases_map[sr_id]["invoice_names"].add(pi.name)
			# If linked at header level, count full invoice amount
			if pi.header_sr == sr_id:
				purchases_map[sr_id]["net_total"] += flt(pi.base_net_total)
				purchases_map[sr_id]["grand_total"] += flt(pi.base_grand_total)
			elif pi.item_sr == sr_id:
				purchases_map[sr_id]["net_total"] += flt(pi.item_net)
				purchases_map[sr_id]["grand_total"] += flt(pi.item_gross or pi.item_net)
		elif pi.header_sr != sr_id and pi.item_sr == sr_id:
			# Additional item on same invoice for this SR
			purchases_map[sr_id]["net_total"] += flt(pi.item_net)
			purchases_map[sr_id]["grand_total"] += flt(pi.item_gross or pi.item_net)

	data = []
	tot_sales_net = 0.0
	tot_sales_grand = 0.0
	tot_purchase_net = 0.0
	tot_purchase_grand = 0.0
	tot_profit = 0.0

	for sr in sr_list:
		linked_si = sales_map.get(sr.name, [])
		s_names = list({s.name for s in linked_si})
		s_net = sum(flt(s.base_net_total) for s in linked_si)
		s_grand = sum(flt(s.base_grand_total) for s in linked_si)

		# If not invoiced but billing total exists, we show billing total as estimated if needed,
		# but strictly per user request: calculate from sales invoice and purchase invoice
		p_data = purchases_map.get(sr.name, {"invoice_names": set(), "net_total": 0.0, "grand_total": 0.0})
		p_names = sorted(list(p_data["invoice_names"]))
		p_net = flt(p_data["net_total"])
		p_grand = flt(p_data["grand_total"])

		gross_profit = flt(s_net - p_net, 2)
		margin_pct = flt((gross_profit / s_net) * 100, 2) if s_net > 0 else 0.0

		tot_sales_net += s_net
		tot_sales_grand += s_grand
		tot_purchase_net += p_net
		tot_purchase_grand += p_grand
		tot_profit += gross_profit

		data.append({
			"service_request": sr.name,
			"date": sr.received_date,
			"customer_name": sr.customer_name or sr.customer,
			"components": ", ".join(components_map.get(sr.name, [])) or "-",
			"status": sr.status,
			"sales_invoices": ", ".join(s_names) or "-",
			"sales_net": s_net,
			"sales_grand": s_grand,
			"purchase_invoices": ", ".join(p_names) or "-",
			"purchase_net": p_net,
			"purchase_grand": p_grand,
			"gross_profit": gross_profit,
			"margin_pct": margin_pct,
		})

	# Summary cards
	overall_margin = flt((tot_profit / tot_sales_net) * 100, 2) if tot_sales_net > 0 else 0.0
	report_summary = [
		{
			"value": tot_sales_net,
			"indicator": "Blue",
			"label": _("Total Invoiced Sales (Net)"),
			"datatype": "Currency",
		},
		{
			"value": tot_purchase_net,
			"indicator": "Orange",
			"label": _("Total Purchase Cost (Net)"),
			"datatype": "Currency",
		},
		{
			"value": tot_profit,
			"indicator": "Green" if tot_profit >= 0 else "Red",
			"label": _("Total Gross Profit"),
			"datatype": "Currency",
		},
		{
			"value": overall_margin,
			"indicator": "Green" if overall_margin >= 0 else "Red",
			"label": _("Overall Margin %"),
			"datatype": "Percent",
		},
	]

	# Bar Chart of Top 10 Jobs
	chart = get_chart(data)

	return data, report_summary, chart


def get_chart(data):
	if not data:
		return None

	# Sort by sales_net desc, take top 10
	sorted_data = sorted(data, key=lambda d: d.get("sales_net", 0), reverse=True)[:10]

	labels = [d["service_request"] for d in sorted_data]
	sales_vals = [d["sales_net"] for d in sorted_data]
	cost_vals = [d["purchase_net"] for d in sorted_data]
	profit_vals = [d["gross_profit"] for d in sorted_data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Sales Revenue"), "values": sales_vals},
				{"name": _("Purchase Cost"), "values": cost_vals},
				{"name": _("Gross Profit"), "values": profit_vals},
			],
		},
		"type": "bar",
		"colors": ["#2563eb", "#f97316", "#22c55e"],
	}
