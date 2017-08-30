/********************************************************************************
 * Copyright 2017 IBM
 *
 *   Licensed under the Apache License, Version 2.0 (the "License");
 *   you may not use this file except in compliance with the License.
 *   You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *   Unless required by applicable law or agreed to in writing, software
 *   distributed under the License is distributed on an "AS IS" BASIS,
 *   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *   See the License for the specific language governing permissions and
 ********************************************************************************/

/*eslint-env node */
var fs = require('fs');
var services = JSON.parse(fs.readFileSync(process.env.SERVICE_INSTANCE_FILE)).services;

var appscan_service = findServiceInstance(services, process.env.SERVICE_INSTANCE);
if (appscan_service) {
	var appscan_name = appscan_service.parameters.name,
		dashboard_url = appscan_service.parameters.dashboard_url,
		user_id = appscan_service.parameters.user_id,
		user_token = appscan_service.parameters.user_token,
		webhook_url = appscan_service.parameters.webhook_url,
		appscan_service_id = appscan_service.service_instance_id;
	console.log('export APPSCAN_INSTANCE_NAME="' + appscan_name + '"');
	console.log('export APPSCAN_SERVICE_ID="' + appscan_service_id + '"');
	console.log('export APPSCAN_SERVER_URL="' + dashboard_url + '"');
	console.log('export APPSCAN_USER_ID="' + user_id + '"');
	console.log('export APPSCAN_USER_TOKEN="' + user_token + '"');
	console.log('export APPSCAN_WEBHOOK_URL="' + webhook_url + '"');
}

function findServiceInstance(services, serviceName) {
	var service = services.filter(function(v) {
		return v.service_id === 'appscan' &&
			(serviceName === '(default)' ||
				v.parameters && v.parameters.name === serviceName);
	});
	if (service.length > 0) {
		return service[0];
	}
}