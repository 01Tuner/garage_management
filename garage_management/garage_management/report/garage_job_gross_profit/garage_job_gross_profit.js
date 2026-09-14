// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.query_reports["Garage Job Gross Profit"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "status",
			label: __("Job Status"),
			fieldtype: "Select",
			options: "\nReceived\nInspecting\nQuoted\nAwaiting Approval\nAwaiting Parts\nRepairing\nTesting\nCompleted\nInvoiced\nDelivered\nOn Hold\nCancelled",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "service_request",
			label: __("Service Request"),
			fieldtype: "Link",
			options: "Service Request",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "gross_profit" && data) {
			if (data.gross_profit > 0) {
				value = `<span style="color:var(--green-600);font-weight:600;">${value}</span>`;
			} else if (data.gross_profit < 0) {
				value = `<span style="color:var(--red-600);font-weight:600;">${value}</span>`;
			}
		}

		if (column.fieldname === "margin_pct" && data) {
			if (data.margin_pct > 0) {
				value = `<span style="color:var(--green-600);font-weight:600;">${value}</span>`;
			} else if (data.margin_pct < 0) {
				value = `<span style="color:var(--red-600);font-weight:600;">${value}</span>`;
			}
		}

		if (column.fieldname === "sales_invoices" && value && value !== "-") {
			const invs = (data.sales_invoices || "").split(", ");
			value = invs
				.map((inv) => `<a href="/app/sales-invoice/${encodeURIComponent(inv)}" class="text-primary">${frappe.utils.escape_html(inv)}</a>`)
				.join(", ");
		}

		if (column.fieldname === "purchase_invoices" && value && value !== "-") {
			const invs = (data.purchase_invoices || "").split(", ");
			value = invs
				.map((inv) => `<a href="/app/purchase-invoice/${encodeURIComponent(inv)}" class="text-primary">${frappe.utils.escape_html(inv)}</a>`)
				.join(", ");
		}

		return value;
	},
};
