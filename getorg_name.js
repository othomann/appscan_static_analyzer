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
var fs = require("fs"),
	request_promise = require('request-promise');

var fileName = process.argv[2];
var config = JSON.parse(fs.readFileSync(fileName));

var rq = {
	method: 'GET',
	url: process.env.CF_CONTROLLER + "/v2/organizations/" + config.organization_id + "/summary",
	json: true,
	headers: {
		'Authorization': process.env.TOOLCHAIN_TOKEN,
		'Content-Type': 'application/json',
		'Accept': 'application/json'
	}
};

return request_promise(rq)
	.then(function(result) {
		config.organization_name = result.name;
		fs.writeFileSync(fileName, config, "UTF-8");
	})
	.catch(function() {
	});