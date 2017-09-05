#!/bin/bash

#********************************************************************************
# Copyright 2015 IBM
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
#********************************************************************************

#############
# Colors    #
#############
export green='\e[0;32m'
export red='\e[0;31m'
export label_color='\e[0;33m'
export no_color='\e[0m' # No Color

##################################################
# Simple function to only run command if DEBUG=1 # 
##################################################
debugme() {
  [[ $DEBUG = 1 ]] && "$@" || :
}
export -f debugme 

set +e
set +x 

###############################
# Configure extension PATH    #
###############################
if [ -n $EXT_DIR ]; then 
    export PATH=$EXT_DIR:$PATH
fi

#########################################
# Configure log file to store errors  #
#########################################
if [ -z "$ERROR_LOG_FILE" ]; then
    ERROR_LOG_FILE="${EXT_DIR}/errors.log"
    export ERROR_LOG_FILE
fi

#################################
# Source git_util file          #
#################################
source ${EXT_DIR}/git_util.sh

################################
# get the extensions utilities #
################################
pushd . >/dev/null
cd $EXT_DIR 
git_retry clone https://github.com/Osthanes/utilities.git utilities
export PYTHONPATH=$EXT_DIR/utilities:$PYTHONPATH
popd >/dev/null

#################################
# Source utilities sh files     #
#################################
source ${EXT_DIR}/utilities/ice_utils.sh
source ${EXT_DIR}/utilities/logging_utils.sh


################################
# Application Name and Version #
################################
# The build number for the builder is used for the version in the image tag 
# For deployers this information is stored in the $BUILD_SELECTOR variable and can be pulled out
if [ -z "$APPLICATION_VERSION" ]; then
    export SELECTED_BUILD=$(grep -Eo '[0-9]{1,100}' <<< "${BUILD_SELECTOR}")
    if [ -z $SELECTED_BUILD ]; then 
        if [ -z $BUILD_NUMBER ]; then 
            export APPLICATION_VERSION=$(date +%s)
        else 
            export APPLICATION_VERSION=$BUILD_NUMBER
        fi
    else
        export APPLICATION_VERSION=$SELECTED_BUILD
    fi 
fi 

# install necessary features
log_and_echo "$INFO" "Setting up prerequisites for IBM Security Static Analyzer.  This will likely take several minutes"
debugme echo "enabling i386 architechture"
sudo dpkg --add-architecture i386 >/dev/null 2>&1
sudo apt-get update >/dev/null 2>&1
debugme echo "installing i386 libraries"
sudo apt-get install -y libc6:i386 libc6-i686 g++-multilib >/dev/null 2>&1

debugme echo "installing bc"
sudo apt-get install -y bc >/dev/null 2>&1
debugme echo "installing unzip"
sudo apt-get install -y unzip >/dev/null 2>&1
debugme echo "done installing prereqs"

if [ -n "$BUILD_OFFSET" ]; then 
    log_and_echo "$INFO" "Using BUILD_OFFSET of $BUILD_OFFSET"
    export APPLICATION_VERSION=$(echo "$APPLICATION_VERSION + $BUILD_OFFSET" | bc)
    export BUILD_NUMBER=$(echo "$BUILD_NUMBER + $BUILD_OFFSET" | bc)
fi 

################################
# Setup archive information    #
################################
if [ -z $WORKSPACE ]; then 
    log_and_echo "$ERROR" "Please set WORKSPACE in the environment properties."
    ${EXT_DIR}/utilities/sendMessage.sh -l bad -m "Please set WORKSPACE in the environment properties."
    exit 1
fi 

if [ -z $ARCHIVE_DIR ]; then 
    log_and_echo "$LABEL" "ARCHIVE_DIR was not set, setting to WORKSPACE/archive."
    export ARCHIVE_DIR="${WORKSPACE}"
fi 

if [ -d $ARCHIVE_DIR ]; then
  log_and_echo "$INFO" "Archiving to $ARCHIVE_DIR"
else 
  log_and_echo "$INFO" "Creating archive directory $ARCHIVE_DIR"
  mkdir $ARCHIVE_DIR 
fi 
export LOG_DIR=$ARCHIVE_DIR

# fetch the current version of utils
cur_dir=`pwd`
cd ${EXT_DIR}
#CLI is too large for extension, so always download, fail if can't
FORCE_NEWEST_CLI=1
if [[ $FORCE_NEWEST_CLI = 1 ]]; then
    wget https://ui.appscan.ibmcloud.com/api/BlueMix/StaticAnalyzer/SAClientUtil?os=linux -O SAClientUtil.zip -o /dev/null
    unzip -o -qq SAClientUtil.zip
    if [ $? -eq 9 ]; then
        log_and_echo "$ERROR" "Unable to download SAClient"
        exit 1
    fi
else
    unzip -o -qq SAClientLocal.zip
fi
cd `ls -d SAClient*/`
export APPSCAN_INSTALL_DIR=`pwd`
cd $cur_dir
export PATH=$APPSCAN_INSTALL_DIR/bin:$PATH
export LD_LIBRARY_PATH=$APPSCAN_INSTALL_DIR/bin:$LD_LIBRARY_PATH
echo `appscan.sh version`

log_and_echo "$LABEL" "Initialization complete"

export TOOLCHAINS_API=https://$( echo $IDS_URL | sed 's!^.*//\([^/]*\)/.*$!\1!g'  | sed 's!devops!devops-api!g' )/v1/toolchains
export SERVICE_INSTANCE_FILE=/tmp/tc_services.json
