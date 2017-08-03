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
	var appscan_id = appscan_service.parameters.name,
		dashboard_url = appscan_service.parameters.dashboard_url,
		user_login = appscan_service.parameters.user_login,
		user_token = appscan_service.parameters.user_token;
	console.log('export APPSCAN_INSTANCE_NAME="' + appscan_id + '"');
	console.log('export APPSCAN_SERVER_URL="' + dashboard_url + '"');
	if (user_login) {
		console.log('export APPSCAN_USER_ID="' + user_login + '"');
	}
	if (user_token) {
		console.log('export APPSCAN_USER_TOKEN="' + user_token + '"');
	}
}

function findServiceInstance(services, serviceName) {
	var newappscan = services.filter(function(v) {
		return v.service_id === 'newappscan' &&
			(serviceName === '(default)' ||
				v.parameters && v.parameters.name === serviceName);
	});
	if (newappscan.length > 0) {
		return newappscan[0];
	}
}