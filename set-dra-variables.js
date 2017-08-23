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

var dra_service = findServiceInstance(services);
if (dra_service) {
	var organization_guid = dra_service.organization_guid,
		cf_controller = dra_service.parameters.cf_controller,
		dra_server = dra_service.parameters.dra_server,
		dlms_server = dra_service.parameters.dlms_server;
	console.log('export ORGANIZATION_GUID=' + organization_guid);
	console.log('export CF_CONTROLLER=' + cf_controller);
	console.log('export DRA_SERVER=' + dra_server);
	console.log('export DLMS_SERVER=' + dlms_server);
	console.log('export DRA_IS_PRESENT=1');
}

function findServiceInstance(services) {
	var service = services.filter(function(v) {
		return v.service_id === 'draservicebroker';
	});
	if (service.length > 0) {
		return service[0];
	}
}