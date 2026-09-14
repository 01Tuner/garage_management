# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

"""
Garage Management hooks
"""

app_name = "garage_management"
app_title = "Garage Management"
app_publisher = "rafeeq"
app_description = "Garage management for ERPNext"
app_email = "muhammedrafeeq93@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

app_include_css = "/assets/garage_management/css/garage_workspace.css?v=5"
app_include_js = "/assets/garage_management/js/service_job_kanban.js?v=5"

after_install = "garage_management.install.after_install"
after_migrate = "garage_management.install.after_migrate"

permission_query_conditions = {
	"Service Request": "garage_management.garage_management.doctype.service_request.service_request.get_permission_query_conditions",
	"Inspection": "garage_management.garage_management.doctype.inspection.inspection.get_permission_query_conditions",
	"Repair Job": "garage_management.garage_management.doctype.repair_job.repair_job.get_permission_query_conditions",
	"Service Job": "garage_management.garage_management.doctype.service_job.service_job.get_permission_query_conditions",
}

has_permission = {
	"Service Request": "garage_management.garage_management.doctype.service_request.service_request.has_permission",
	"Inspection": "garage_management.garage_management.doctype.inspection.inspection.has_permission",
	"Repair Job": "garage_management.garage_management.doctype.repair_job.repair_job.has_permission",
	"Service Job": "garage_management.garage_management.doctype.service_job.service_job.has_permission",
}

doctype_js = {
	"Purchase Invoice": "public/js/purchase_invoice.js",
}

doc_events = {
	"Quotation": {
		"on_trash": "garage_management.api.service_job.on_quotation_trash",
		"on_cancel": "garage_management.api.service_job.on_quotation_cancel",
	},
	"Sales Order": {
		"on_trash": "garage_management.api.service_job.on_sales_order_trash",
		"on_cancel": "garage_management.api.service_job.on_sales_order_cancel",
	},
	"Sales Invoice": {
		"on_submit": "garage_management.api.service_request.on_sales_invoice_submit",
		"on_cancel": "garage_management.api.service_job.on_sales_invoice_cancel_hook",
		"on_trash": "garage_management.api.service_job.on_sales_invoice_trash",
	},
	"Purchase Invoice": {
		"validate": "garage_management.api.purchase_invoice.validate_purchase_invoice",
	},
	"Purchase Order": {
		"validate": "garage_management.api.purchase_invoice.validate_purchase_order",
	},
}

