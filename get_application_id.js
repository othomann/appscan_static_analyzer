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
var list_app_names = fs.readFileSync(process.argv[2]);
var app_name = process.argv[3];
console.log("app_name=>" + app_name + "<");
function scan_app_names(lines) {
	for(var lineIndex = 0; lineIndex < lines.length; lineIndex++) {
		var line = lines[lineIndex];
		var index = line.lastIndexOf('[');
		var possible_app_name = line.substr(0, index).trim();
		if (app_name) {
			if (app_name === possible_app_name) {
				var app_id = line.substr(index + 1).trim();
				app_id = app_id.substring(0, app_id.indexOf(']')).trim();
				console.log("export APPSCAN_APP_ID=" + app_id);
				return;
			}
		}
	}
}
var lines = list_app_names.toString('UTF-8').split(/\r\n|\n/);

scan_app_names(lines);