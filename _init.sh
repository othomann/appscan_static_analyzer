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

log_and_echo "$INFO" "APPLICATION_VERSION: $APPLICATION_VERSION"

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

#############################
# Install Cloud Foundry CLI #
#############################
cf help &> /dev/null
RESULT=$?
if [ $RESULT -eq 0 ]; then
    # if already have an old version installed, save a pointer to it
    export OLDCF_LOCATION=`which cf`
fi
# get the newest version
log_and_echo "$INFO" "Installing Cloud Foundry CLI"
pushd . >/dev/null
cd $EXT_DIR 
curl --silent -o cf-linux-amd64.tgz -v -L https://cli.run.pivotal.io/stable?release=linux64-binary &>/dev/null 
gunzip cf-linux-amd64.tgz &> /dev/null
tar -xvf cf-linux-amd64.tar  &> /dev/null
cf help &> /dev/null
RESULT=$?
if [ $RESULT -ne 0 ]; then
    log_and_echo "$ERROR" "Could not install the cloud foundry CLI"
    ${EXT_DIR}/utilities/sendMessage.sh -l bad -m "Could not install the cloud foundry CLI"
    exit 1
fi  
popd >/dev/null
log_and_echo "$SUCCESSFUL" "Successfully installed Cloud Foundry CLI"

##########################################
# setup bluemix env
##########################################
# attempt to  target env automatically
# ${EXT_DIR}/cf api https://api.stage1.ng.bluemix.net
# ${EXT_DIR}/cf login -u Olivier_Thomann@ca.ibm.com -p B1ykqu44!
CF_API=$(${EXT_DIR}/cf api)
RESULT=$?
debugme echo "CF_API: ${CF_API}"
if [ $RESULT -eq 0 ]; then
    # find the bluemix api host
    export BLUEMIX_API_HOST=`echo $CF_API  | awk '{print $3}' | sed '0,/.*\/\//s///'`
    echo $BLUEMIX_API_HOST | grep 'stage1'
    if [ $? -eq 0 ]; then
        # on staging, make sure bm target is set for staging
        export BLUEMIX_TARGET="staging"
        export BLUEMIX_API_HOST="api.stage1.ng.bluemix.net"
    else
        # on prod, make sure bm target is set for prod
        export BLUEMIX_TARGET="prod"
        export BLUEMIX_API_HOST="api.ng.bluemix.net"
    fi
elif [ -n "$BLUEMIX_TARGET" ]; then
    # cf not setup yet, try manual setup
    if [ "$BLUEMIX_TARGET" == "staging" ]; then 
        log_and_echo "$INFO" "Targetting staging Bluemix"
        export BLUEMIX_API_HOST="api.stage1.ng.bluemix.net"
    elif [ "$BLUEMIX_TARGET" == "prod" ]; then 
        log_and_echo "$INFO" "Targetting production Bluemix"
        export BLUEMIX_API_HOST="api.ng.bluemix.net"
    else
        log_and_echo "$INFO" "$ERROR" "Unknown Bluemix environment specified"
    fi
else
    log_and_echo "$INFO" "Targetting production Bluemix"
    export BLUEMIX_API_HOST="api.ng.bluemix.net"
fi

# we are already logged in.  Simply check via cf command 
log_and_echo "$LABEL" "Logging into IBM Container Service using credentials passed from IBM DevOps Services"
cf target >/dev/null 2>/dev/null
RESULT=$?
if [ ! $RESULT -eq 0 ]; then
    log_and_echo "$INFO" "cf target did not return successfully.  Login failed."
fi 

# check login result 
if [ $RESULT -eq 1 ]; then
    log_and_echo "$ERROR" "Failed to login to IBM Bluemix"
    ${EXT_DIR}/utilities/sendMessage.sh -l bad -m "Failed to login to IBM Bluemix"
    exit $RESULT
else 
    log_and_echo "$SUCCESSFUL" "Successfully logged into IBM Bluemix"
fi 

log_and_echo "$INFO" "BLUEMIX_API_HOST: ${BLUEMIX_API_HOST}"
log_and_echo "$INFO" "BLUEMIX_TARGET: ${BLUEMIX_TARGET}"

export APPSCAN_ENV=https://appscan-test.bluemix.net

# fetch the current version of utils
cur_dir=`pwd`
cd ${EXT_DIR}
#CLI is too large for extension, so always download, fail if can't
FORCE_NEWEST_CLI=1
if [[ $FORCE_NEWEST_CLI = 1 ]]; then
    wget ${APPSCAN_ENV}/api/BlueMix/StaticAnalyzer/SAClientUtil?os=linux -O SAClientUtil.zip -o /dev/null
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

############################
# setup DRA                #
############################
pushd $EXT_DIR >/dev/null
git clone https://github.com/jparra5/dra_utilities.git dra_utilities
popd >/dev/null

# Call common initialization
source $EXT_DIR/dra_utilities/init.sh

log_and_echo "$LABEL" "Initialization complete"

export TOOLCHAINS_API=https://$( echo $IDS_URL | sed 's!^.*//\([^/]*\)/.*$!\1!g'  | sed 's!devops!devops-api!g' )/v1/toolchains
export SERVICE_INSTANCE_FILE=/tmp/tc_services.json
