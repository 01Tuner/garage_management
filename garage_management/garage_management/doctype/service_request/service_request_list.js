frappe.listview_settings["Service Request"] = {
	add_fields: [
		"status",
		"customer_name",
		"priority",
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
	onload(listview) {
		const route = frappe.get_route();
		if (route[0] === "List" && route[1] === "Service Request" && (!route[2] || route[2] === "List")) {
			frappe.set_route("List", "Service Request", "Kanban", "Service Request by Status");
		}
	},
};
