#!/bin/bash
#***************************************************************************
# Copyright 2015, 2017 IBM
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#***************************************************************************

function dra_commands {
    echo -e "${no_color}"
    dra_grunt_command="grunt --gruntfile=$EXT_DIR/node_modules/grunt-idra3/idra.js"
    dra_grunt_command="$dra_grunt_command -testResult=\"$1\""
    dra_grunt_command="$dra_grunt_command -stage=\"$3\""
    dra_grunt_command="$dra_grunt_command -drilldownUrl=\"$4\""

#    debugme echo -e "dra_grunt_command with log & stage: \n\t$dra_grunt_command"
    echo -e "dra_grunt_command with log & stage: \n\t$dra_grunt_command"

    if [ -n "$2" ] && [ "$2" != " " ]; then

#        debugme echo -e "\tartifact: '$2' is defined and not empty"
        echo -e "\tartifact: '$2' is defined and not empty"
        dra_grunt_command="$dra_grunt_command -artifact=\"$2\""
#        debugme echo -e "\tdra_grunt_command: \n\t\t$dra_grunt_command"
        echo -e "\tdra_grunt_command: \n\t\t$dra_grunt_command"


    else
        debugme echo -e "\tartifact: '$2' is not defined or is empty"
        debugme echo -e "${no_color}"
    fi


    echo -e "FINAL dra_grunt_command: $dra_grunt_command"
    echo -e "${no_color}"
#    debugme echo -e "FINAL dra_grunt_command: $dra_grunt_command"
#    debugme echo -e "${no_color}"


    eval "$dra_grunt_command -f --no-color"
    GRUNT_RESULT=$?

#    debugme echo "GRUNT_RESULT: $GRUNT_RESULT"
    echo "GRUNT_RESULT: $GRUNT_RESULT"

    if [ $GRUNT_RESULT -ne 0 ]; then
        exit 1
    fi

    echo -e "${no_color}"
}

for zipFile in appscan-*.zip;
do
    # unzip the appscan results
    resultDirectory="appscanResultDir"
    unzip $zipFile -d $resultDirectory

    # full report location
    export DRA_LOG_FILE="$EXT_DIR/$resultDirectory/Report-final.xml"
    # summary report location. Replace appscan-app.zip with appscan-app.json.
    export DRA_SUMMARY_FILE="$EXT_DIR/${zipFile%.zip}.json"

    # pass appscan report url to DRA
    #json=`cat ${DRA_SUMMARY_FILE}`
    #appscan_url=`python -c "import json; obj = json.loads('$json'); print( obj['url'] );"`
    appscan_url="https://ui.appscan.ibmcloud.com/AsoCUI/serviceui/main/myapps/oneapp/$APPSCAN_APP_ID/scans"

    # Upload to DRA

    # upload the full appscan report
    dra_commands "${DRA_LOG_FILE}" "${zipFile}" "staticsecurityscan" "${appscan_url}"
    # upload the summary appscan report
    #dra_commands "${DRA_SUMMARY_FILE}" "${DRA_SUMMARY_FILE}" "staticsecurityscan"

    # Clean up directory
    rm -r $resultDirectory
done
