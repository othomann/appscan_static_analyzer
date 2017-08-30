/*eslint-env node */
var request_promise = require('request-promise'),
	fs = require('fs'),
	config = JSON.parse(fs.readFileSync(process.argv[2]));

var rq = {
	method: 'GET',
	url: config.cf_controller + "/v2/organizations/" + config.organization_id + "/summary",
	json: true,
	headers: {
		'Authorization': config.toolchain_token,
		'Content-Type': 'application/json',
		'Accept': 'application/json'
	}
};

return request_promise(rq)
	.then(function(result) {
		config.organization_name = result.name;
		config.newdate = new Date();
		fs.writeFileSync(process.argv[2], JSON.stringify(config, null, '\t'), 'UTF-8');
	})
	.catch(function(err) {
		console.log(err.message);
	});