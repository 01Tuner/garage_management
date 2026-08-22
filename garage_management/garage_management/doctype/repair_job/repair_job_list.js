frappe.listview_settings["Repair Job"] = {
	add_fields: ["status", "customer_name", "assigned_to", "service_request", "job_type"],
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			"In Progress": "cyan",
			Testing: "pink",
			Completed: "green",
			Cancelled: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
