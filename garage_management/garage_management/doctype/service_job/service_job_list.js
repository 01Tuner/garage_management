frappe.listview_settings["Service Job"] = {
	add_fields: [
		"status",
		"customer_name",
		"priority",
		"technician",
		"job_type",
		"complaint",
		"billing_total",
		"quotation",
		"sales_order",
		"sales_invoice",
		"mobile_no",
	],
	get_indicator(doc) {
		const colors = {
			Received: "blue",
			Inspecting: "orange",
			Quoted: "yellow",
			"Awaiting Approval": "purple",
			"In Progress": "cyan",
			Testing: "pink",
			Completed: "green",
			Invoiced: "green",
			Delivered: "darkgrey",
			"On Hold": "orange",
			Cancelled: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
