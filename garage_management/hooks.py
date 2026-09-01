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

app_include_css = "/assets/garage_management/css/garage_workspace.css"
app_include_js = "/assets/garage_management/js/service_job_kanban.js"

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

doc_events = {
	"Sales Invoice": {
		"on_submit": "garage_management.api.service_request.on_sales_invoice_submit",
		"on_cancel": "garage_management.api.service_request.on_sales_invoice_cancel",
	}
}
