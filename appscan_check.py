#!/usr/bin/python

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

import json
import logging
import logging.handlers
import os
import os.path
import sys
import time
import timeit
from datetime import datetime
from subprocess import call, Popen, PIPE
import python_utils

DEFAULT_SCANNAME="staticscan"
DEFAULT_OLD_SCANS_TO_KEEP="5"
DEFAULT_OLD_SCANS_TO_KEEP_INT=5

# check cli args, set globals appropriately
def parse_args ():
    parsed_args = {}
    parsed_args['loginonly'] = False
    parsed_args['forcecleanup'] = False
    parsed_args['checkstate'] = False
    parsed_args['debug'] = False
    parsed_args['help'] = False
    for arg in sys.argv:
        if arg == "--loginonly":
            # only login, no scanning or submission
            parsed_args['loginonly'] = True
        if arg == "--forcecleanup":
            # cleanup/cancel all complete jobs, and delete irx files
            parsed_args['forcecleanup'] = True
        if arg == "--checkstate":
            # just check state of existing jobs, don't scan or submit
            # any new ones
            parsed_args['checkstate'] = True
        if arg == "--debug":
            # enable debug mode, can also be done with python_utils.DEBUG env var
            parsed_args['debug'] = True
            python_utils.DEBUG = "1"
        if arg == "--help":
            # just print help and return
            parsed_args['help'] = True

    return parsed_args

# print a quick usage/help statement
def print_help ():
    print "usage: appscan_check.py [options]"
    print
    print "\toptions:"
    print "\t   --loginonly    : get credentials and login to appscan only"
    print "\t   --forcecleanup : on exit, force removal of pending jobs from this run"
    print "\t   --checkstate   : check state of existing job(s), no new submission"
    print "\t   --debug        : get additional debug output"
    print "\t   --help         : print this help message and exit"
    print


# create a template for a current scan.  this will be in the format
# "<scanname>-<version>-" where scanname comes from env var 
# 'SUBMISSION_NAME', and version comes from env var 'APPLICATION_VERSION'
def get_scanname_template (include_version=True):
    # check the env for name of the scan, else use default
    if os.environ.get('SUBMISSION_NAME'):
        scanname=os.environ.get('SUBMISSION_NAME')
    elif os.environ.get('IDS_PROJECT_NAME'):
        scanname=os.environ.get('IDS_PROJECT_NAME').replace(" | ", "-")
    else:
        scanname=DEFAULT_SCANNAME

    if include_version:
        # if we have an application version, append it to the scanname
        if os.environ.get('APPLICATION_VERSION'):
            scanname = scanname + "-" + os.environ.get('APPLICATION_VERSION')

    scanname = scanname + "-"

    return scanname

# given userid and password, attempt to authenticate to appscan for
# future calls
def appscan_login (userid, password):
    proc = Popen(["appscan.sh api_login -u " + userid + " -P " + password + " -persist"], 
                      shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate();

    if not "Authenticated successfully." in out:
        raise Exception("Unable to login to Static Analysis service")

# callout to appscan to prepare a current irx file, return a set of
# the files created by the prepare
def appscan_prepare ():

    # sadly, prepare doesn't tell us what file it created, so find
    # out by a list compare before/after
    oldIrxFiles = []
    for file in os.listdir("."):
        if file.endswith(".irx"):
            oldIrxFiles.append(file)

    # clean up the appscan client log so we can dump it on error if needed
    # and only see the error from this call
    logfileName = None
    appscanDir = os.environ.get('APPSCAN_INSTALL_DIR')
    if appscanDir:
        logfileName = appscanDir+"/logs/client.log"
        if os.path.isfile( logfileName ):
            os.remove( logfileName )

    proc = Popen(["appscan.sh prepare -t"], 
                 shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate();

    if not "IRX file generation successful" in out:
        if "An IRX file was created, but it may be incomplete" in err:
            # some jar/war/ear files were not scannable, but some were.
            # attempt the submission
            python_utils.LOGGER.warning(out)
            python_utils.LOGGER.warning("Not all files could be scanned, but the scan has been submitted for those which were")
        else:
            if python_utils.DEBUG:
                call(["grep -H \".*\" logs/*.log"], shell=True, cwd=appscanDir)
            raise Exception("Unable to prepare code for analysis by Static Analysis service: " + 
                            err)

    # what files are there now?
    newIrxFiles = []
    for file in os.listdir("."):
        if file.endswith(".irx"):
            newIrxFiles.append(file)
    # which files are new?
    newIrxFiles = set(newIrxFiles).difference(oldIrxFiles)

    logMessage = "Generated scans as file(s):"
    for file in newIrxFiles:
        logMessage = logMessage + "\n\t" + file

    python_utils.LOGGER.info(logMessage)

    return newIrxFiles

def send_job_id_to_toolint_broker (jobId):
    python_utils.LOGGER.info("job id: " + jobId)
    if os.environ.get('DRA_IS_PRESENT') == "1":
        # All information to send to the toolint-broker
        python_utils.LOGGER.info("DRA is present: " + jobId)
        appscan_result_file = os.environ.get('EXT_DIR') + '/appscan-result-toolint.json'
        appscan_result = {
          'appscan_app_id' : os.environ.get('APPSCAN_APP_ID'),
          'appscan_service_id' : os.environ.get('APPSCAN_SERVICE_ID'),
          'build_number': os.environ.get('BUILD_NUMBER'),
          'cf_controller' : os.environ.get('CF_CONTROLLER'),
          'dlms_server' : os.environ.get('DLMS_SERVER'),
          'dra_server' : os.environ.get('DRA_SERVER'),
          'job_id' : jobId,
          'key_id' :  os.environ.get('APPSCAN_USER_ID'),
          'key_secret' : os.environ.get('APPSCAN_USER_TOKEN'),
          'logical_app_name': os.environ.get('LOGICAL_APP_NAME'),
          'organization_id' : os.environ.get('ORGANIZATION_GUID'),
          'scan_type' : 'staticsecurityscan',
          'toolchain_id': os.environ.get('PIPELINE_TOOLCHAIN_ID')
        };
        python_utils.LOGGER.info("Write file " + appscan_result_file + " on disk")
        with open(appscan_result_file, 'w') as outfile:
            json.dump(appscan_result, outfile, sort_keys = True)
        # send the resulting json to the toolint-broker to be stored in the cloudant db

def printVariable(str):
    variable = os.environ.get(str);
    if variable is None :
        python_utils.LOGGER.info("No value defined for " + str)
    else:
        python_utils.LOGGER.info(str + ": " + variable)

# submit a created irx file to appscan for analysis
def appscan_submit (filelist):
    if filelist==None:
        raise Exception("No files to analyze")

    scanlist = []
    index = 0
    for filename in filelist:
        submit_scanname = get_scanname_template() + str(index)
        proc = Popen(["appscan.sh queue_analysis -f " + filename + " -n " + submit_scanname + " -a " + os.environ.get('APPSCAN_APP_ID') + ""], 
                          shell=True, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate();

        transf_found = False
        for line in out.splitlines() :
            python_utils.LOGGER.debug("Submit response line: " + line)
            if "100% transferred" in line:
                # done transferring
                transf_found = True
            elif not transf_found:
                # not done transferring yet
                continue
            elif line:
                # done, if line isn't empty, is an id
                scanlist.append(line)
                python_utils.LOGGER.info("Job for file " + filename + " was submitted as scan " + submit_scanname + " and assigned id " + line)
                send_job_id_to_toolint_broker(line)
            else:
                # empty line, skip it
                continue
        if err:
            python_utils.LOGGER.warning("Submit error response: " + str(err))
        index = index + 1
    return scanlist, err


# get appscan list of current jobs
def appscan_list ():
    proc = Popen(["appscan.sh list"], 
                      shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate();

    scanlist = []
    for line in out.splitlines() :
        if "No analysis jobs" in line:
            # no jobs, return empty list
            python_utils.LOGGER.info("No analysis jobs found")
            return []
        elif line:
            # done, if line isn't empty, is an id
            scanlist.append(line)
        else:
            # empty line, skip it
            continue
    python_utils.LOGGER.info("{} analysis jobs found: {}".format(len(scanlist), str(scanlist)))
    return scanlist

# translate a job state to a pretty name
# CLI now returns the string, keeping in case needed later and to have a list of possible stages
def get_state_name (state):
    return {
        0 : "Pending",
        1 : "Starting",
        2 : "Running",
        3 : "FinishedRunning",
        4 : "FinishedRunningWithErrors",
        5 : "PendingSupport",
        6 : "Ready",
        7 : "ReadyIncomplete",
        8 : "FailedToScan",
        9 : "ManuallyStopped",
        10 : "None",
        11 : "Initiating",
        12 : "MissingConfiguration",
        13 : "PossibleMissingConfiguration"
    }.get(state, "Unknown")

# translate a job state from a name to a number
def get_state_num (state):
    val = {
        "pending" : 0,
        "starting" : 1,
        "running" : 2,
        "finishedrunning" : 3,
        "finishedrunningwitherrors" : 4,
        "pendingsupport" : 5,
        "ready" : 6,
        "readyincomplete" : 7,
        "failedtoscan" : 8,
        "manuallystopped" : 9,
        "none" : 10,
        "initiating" : 11,
        "missingconfiguration" : 12,
        "possiblemissingconfiguration" : 13
    }.get(state.lower().strip(), 14)
    python_utils.LOGGER.debug("Getting number for state: \""+str(state)+"\" ("+str(val)+")")
    return val

# given a state, is the job completed
def get_state_completed (state):
    return {
        0 : False,
        1 : False,
        2 : False,
        3 : True,
        4 : True,
        5 : False,
        6 : True,
        7 : True,
        8 : True,
        9 : True,
        10 : True,
        11 : False,
        12 : True,
        13 : True
    }.get(get_state_num(state), True)

# given a state, was it completed successfully
def get_state_successful (state):
    return {
        0 : False,
        1 : False,
        2 : False,
        3 : True,
        4 : False,
        5 : False,
        6 : True,
        7 : False,
        8 : False,
        9 : False,
        10 : False,
        11 : False,
        12 : False,
        13 : False
    }.get(get_state_num(state), False)

# get status of a given job
def appscan_status (jobid):
    if jobid == None:
        raise Exception("No jobid to check status")

    proc = Popen(["appscan.sh status -i " + str(jobid)], 
                      shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate();

    if "request is invalid" in err:
        if python_utils.DEBUG:
            python_utils.LOGGER.debug("error getting status: " + str(err))
        raise Exception("Invalid jobid")

    retval = str(out)

    return retval

# cancel an appscan job
def appscan_cancel (jobid):
    if jobid == None:
        return

    proc = Popen(["appscan.sh cancel -i " + str(jobid)], 
                      shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()

# parse a key=value line, return value
def parse_key_eq_val (line):
    if line == None:
        return None

    eqIndex = line.find("=");
    if eqIndex != -1:
        return line[eqIndex+1:]
    else:
        return None

# extended info on a current appscan job.  this comes back in a form
# similar to:
#NLowIssues=0
#ReadStatus=2
#NHighIssues=0
#Name=appscan.zip
#ScanEndTime=2014-11-20T13:56:04.497Z
#Progress=0
#RemainingFreeRescanMinutes=0
#ParentJobId=00000000-0000-0000-0000-000000000000
#EnableMailNotifications=false
#JobStatus=6
#NInfoIssues=0
#JobId=9b344fc7-bc70-e411-b922-005056924f9b
#NIssuesFound=0
#CreatedAt=2014-11-20T13:54:49.597Z
#UserMessage=Scan completed successfully. The report is ready.
#NMediumIssues=0
#Result=1
#
# parse it and return useful parts.  in particular, returns
# a dict containing fields for "NLowIssues", "ReadStatus", et al
# per the list above
def appscan_info (jobid):

    # setup default (empty) return
    return_info = {}
    return_info['NLowIssues'] = 0
    return_info['ReadStatus'] = 0
    return_info['NHighIssues'] = 0
    return_info['Name'] = ""
    return_info['ScanEndTime'] = None
    return_info['Progress'] = 0
    return_info['RemainingFreeRescanMinutes'] = 0
    return_info['ParentJobId'] = ""
    return_info['EnableMailNotifications'] = False
    return_info['JobStatus'] = 0
    return_info['NInfoIssues'] = 0
    return_info['JobId'] = ""
    return_info['NIssuesFound'] = 0
    return_info['CreatedAt'] = None
    return_info['UserMessage'] = ""
    return_info['NMediumIssues'] = 0
    return_info['Result'] = 0

    if jobid == None:
        return return_info

    command = "appscan.sh info -i " + str(jobid)
    proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate();

    for line in out.splitlines() :
        if "NLowIssues=" in line:
            # number of low severity issues found in the scan
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['NLowIssues'] = int(tmpstr)
                except ValueError:
                    return_info['NLowIssues']= 0

        elif "NMediumIssues=" in line:
            # number of medium severity issues found in the scan
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['NMediumIssues'] = int(tmpstr)
                except ValueError:
                    return_info['NMediumIssues'] = 0

        elif "NHighIssues=" in line:
            # number of high severity issues found in the scan
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['NHighIssues'] = int(tmpstr)
                except ValueError:
                    return_info['NHighIssues'] = 0

        elif "NInfoIssues=" in line:
            # number of info severity issues found in the scan
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['NInfoIssues'] = int(tmpstr)
                except ValueError:
                    return_info['NInfoIssues'] = 0

        elif "NIssuesFound=" in line:
            # total number of issues found in the scan
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['NIssuesFound'] = int(tmpstr)
                except ValueError:
                    return_info['NIssuesFound'] = 0

        elif "Progress=" in line:
            # current scan progress (0-100)
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['Progress'] = int(tmpstr)
                except ValueError:
                    return_info['Progress'] = 0

        elif "RemainingFreeRescanMinutes=" in line:
            # what the name says
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['RemainingFreeRescanMinutes'] = int(tmpstr)
                except ValueError:
                    return_info['RemainingFreeRescanMinutes'] = 0

        elif "JobStatus=" in line:
            # current job status
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['JobStatus'] = int(tmpstr)
                except ValueError:
                    return_info['JobStatus'] = 0

        elif "ReadStatus=" in line:
            # not sure what this is
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['ReadStatus'] = int(tmpstr)
                except ValueError:
                    return_info['ReadStatus'] = 0

        elif "Result=" in line:
            # final return code
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['Result'] = int(tmpstr)
                except ValueError:
                    return_info['Result'] = 0

        elif "ScanEndTime=" in line:
            # timestamp when this scan completed
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['ScanEndTime'] = datetime.strptime(tmpstr, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    return_info['ScanEndTime'] = None

        elif "CreatedAt=" in line:
            # timestamp when this job was created
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                try:
                    return_info['CreatedAt'] = datetime.strptime(tmpstr, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    return_info['CreatedAt'] = None

        elif "Name=" in line:
            # job name
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                return_info['Name'] = tmpstr

        elif "JobId=" in line:
            # job ID
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                return_info['JobId'] = tmpstr

        elif "ParentJobId=" in line:
            # parent job ID
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                return_info['ParentJobId'] = tmpstr

        elif "UserMessage=" in line:
            # user displayable message, current job state
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                return_info['UserMessage'] = tmpstr

        elif "EnableMailNotifications=" in line:
            # are email notifications setup (doesn't matter, we don't use it)
            tmpstr = parse_key_eq_val(line)
            if tmpstr != None:
                if tmpstr.lower() in ("yes", "true"):
                    return_info['EnableMailNotifications'] = True
                else:
                    return_info['EnableMailNotifications'] = False

    return return_info

# get the result file for a given job
def appscan_get_result (jobid, scan_name):
    if jobid == None:
        raise Exception("No jobid to get results")

    # App name might have a space.
    scan_name = scan_name.replace(" ", "-");

    # Get the appscan zip file
    proc = Popen(["appscan.sh get_result -i " + str(jobid) + " -d appscan-" + str(scan_name) + ".zip -t zip"],
                      shell=True, stdout=PIPE, stderr=PIPE, cwd=os.environ.get('EXT_DIR'))
    out, err = proc.communicate();


    print "Out = " + out
    print "Err = " + err

# get the result file for a given job
def save_job_result (scan_name, job_result):

    # App name might have a space.
    scan_name = scan_name.replace(" ", "-");

    # Store the job result summary
    with open(os.environ.get('EXT_DIR') + "/appscan-" + str(scan_name) + ".json", 'w') as outfile:
        json.dump(job_result, outfile, sort_keys = True)

# get the result file for a given job
def upload_results_to_dra ():
    proc = Popen(["dra.sh"],
                      shell=True, stdout=PIPE, stderr=PIPE, cwd=os.environ.get('EXT_DIR'))
    out, err = proc.communicate();


    print "Out = " + out
    print "Err = " + err

# if the job we would run is already up (and either pending or complete),
# we just want to get state (and wait for it if needed), not create a whole
# new submission.  for the key, we use the job name, compared to the
# name template as per get_scanname_template()
def check_for_existing_job ( ignore_older_jobs = True):
    alljobs = appscan_list()
    if alljobs == None:
        # no jobs, ours can't be there
        return None

    # get the name we're looking for
    job_name = get_scanname_template( include_version = ignore_older_jobs )
    joblist = []
    found = False
    for jobid in alljobs:
        results = appscan_info(jobid)
        python_utils.LOGGER.debug("Results for "+jobid+": "+ str(results))
        if results["Name"].startswith(job_name):
            joblist.append(jobid)
            found = True

    if found:
        return joblist
    else:
        return None

# don't want to have too many old copies of the job hanging out, it
# makes a mess and is hard to read.  prune old copies here
def cleanup_old_jobs ():
    # see how many copies we're going to keep
    try:
        count_to_keep = int(os.getenv('OLD_SCANS_TO_KEEP', DEFAULT_OLD_SCANS_TO_KEEP))
    except ValueError:
        count_to_keep = DEFAULT_OLD_SCANS_TO_KEEP_INT

    # if the count to keep is 0 or negative, keep all copies
    if count_to_keep < 1:
        return

    joblist = check_for_existing_job( ignore_older_jobs = False )
    if joblist == None or len(joblist) <= count_to_keep:
        # related job count < number of jobs too keep, do nothing
        return

    # too many jobs!  remove the oldest ones (cancel if necessary)
    if python_utils.DEBUG:
        python_utils.LOGGER.debug("Found " + str(len(joblist)) + " jobs pending with limit " + str(count_to_keep))

    # make a sorted list of these jobs (yes, this is O(n**2) algorithm, but
    # this should always be a fairly short list of scans)
    s_jobs = []
    for job in joblist:
        results = appscan_info(job)
        # if no results or time, this is not a valid job, skip it
        if (results['CreatedAt'] == None):
            continue
        # put it in the right spot in the list
        i = 0
        while i < len(s_jobs):
            if results['CreatedAt'] > s_jobs[i]['CreatedAt']:
                # found right place
                if python_utils.DEBUG:
                    python_utils.LOGGER.debug("Insert job " + str(results['Name']) + " at index " + str(i) + " for timestamp " + str(results['CreatedAt']))
                s_jobs.insert(i, results)
                break
            i += 1
        if i==len(s_jobs):
            # right place is the end
            if python_utils.DEBUG:
                python_utils.LOGGER.debug("Append job " + str(results['Name']) + " at index " + str(i) + " for timestamp " + str(results['CreatedAt']))
            s_jobs.append(results)

    # now cleanup all jobs after the 'n' we're supposed to keep
    for index, res in enumerate(s_jobs):
        if index<count_to_keep:
            if python_utils.DEBUG:
                python_utils.LOGGER.debug("keeping: " + str(index) + " \"" + res['Name'] + "\" : " + str(res['JobId']))
        else:
            if python_utils.DEBUG:
                python_utils.LOGGER.debug("cleaning: " + str(index) + " \"" + res['Name'] + "\" : " + str(res['JobId']))
            appscan_cancel(res['JobId'])
    # and we're done

# wait for a given set of scans to complete and, if successful,
# download the results
def wait_for_scans (joblist):
    # create array of the jon results in json format
    jobResults = []
    # were all jobs completed on return
    all_jobs_complete = True
    # number of high sev issues in completed jobs
    high_issue_count = 0
    med_issue_count=0
    python_utils.LOGGER.debug("Waiting for joblist: "+str(joblist))
    dash = os.environ.get('APPSCAN_SERVER_URL')
    for jobid in joblist:
        try:
            while True:
                state = appscan_status(jobid)
                python_utils.LOGGER.info("Job " + str(jobid) + " in state " + state)
                if get_state_completed(state):
                    results = appscan_info(jobid)
                    if get_state_successful(state):
                        high_issue_count += results["NHighIssues"]
                        med_issue_count += results["NMediumIssues"]
                        python_utils.LOGGER.info("Analysis successful (" + results["Name"] + ")")
                        #print "\tOther Message : " + msg

                        job_result = {  'job_name': results["Name"],
                                        'job_id': jobid,
                                        'status': "successful",
                                        'high_severity_issues': int(str(results["NHighIssues"])),
                                        'medium_severity_issues': int(str(results["NMediumIssues"])),
                                        'low_severity_issues': int(str(results["NLowIssues"])),
                                        'info_severity_issues': int(str(results["NInfoIssues"])),
                                        'url': dash}

                        # Search for file name results["Name"] + "*.zip"
                        if os.environ.get('DRA_IS_PRESENT') == "1":
                            appscan_get_result(jobid, results["Name"]);
                            save_job_result(results["Name"], job_result);

                        #appscan_get_result(jobid)
                        print python_utils.LABEL_GREEN + python_utils.STARS
                        print "Analysis successful for job \"" + results["Name"] + "\""
                        print "\tHigh Severity Issues   : " + str(results["NHighIssues"])
                        print "\tMedium Severity Issues : " + str(results["NMediumIssues"])
                        print "\tLow Severity Issues    : " + str(results["NLowIssues"])
                        print "\tInfo Severity Issues   : " + str(results["NInfoIssues"])
                        if dash != None:
                            print "See detailed results at: " + python_utils.LABEL_COLOR + " " + dash
                            f = open("result_url","w")
                            f.write(dash)
                            f.close()
                        print python_utils.LABEL_GREEN + python_utils.STARS + python_utils.LABEL_NO_COLOR

                        # append results to the jobResults for the json format
                        jobResults.append(job_result)
                    else: 
                        python_utils.LOGGER.info("Analysis unsuccessful (" + results["Name"] + ") with message \"" + results["UserMessage"] + "\"")

                        # append results to the jobResults for the json format
                        jobResults.append({'job_name': results["Name"], 
                                           'job_id': jobid, 
                                           'status': "unsuccessful"})

                    break
        except Exception, e:
            # bad id, skip it
            if python_utils.DEBUG:
                python_utils.LOGGER.debug("exception in wait_for_scans: " + str(e))

    # generate appscan-result.json file 
    appscan_result = {'all_jobs_complete': all_jobs_complete, 
                      'high_issue_count': high_issue_count, 
                      'medium_issue_count': med_issue_count,
                      'job_results': jobResults}
    appscan_result_file = './appscan-result.json'
    with open(appscan_result_file, 'w') as outfile:
        json.dump(appscan_result, outfile, sort_keys = True)

    if os.environ.get('DRA_IS_PRESENT') == "1":
        upload_results_to_dra()

    return all_jobs_complete, high_issue_count, med_issue_count

# begin main execution sequence

try:
    parsed_args = parse_args()
    if parsed_args['help']:
        print_help()
        sys.exit(0)

    python_utils.LOGGER = python_utils.setup_logging()
    # send slack notification 
    if os.path.isfile("%s/utilities/sendMessage.sh" % python_utils.EXT_DIR):
        command='{path}/utilities/sendMessage.sh -l info -m \"Starting static security scan\"'.format(path=python_utils.EXT_DIR)
        if python_utils.DEBUG:
            print "running command " + command 
        proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
        out, err = proc.communicate();
        python_utils.LOGGER.debug(out)
    else:
        if python_utils.DEBUG:
            print "sendMessage.sh not found, notifications not attempted"
    
    python_utils.WAIT_TIME = python_utils.get_remaining_wait_time(first = True)
    python_utils.LOGGER.info("Connecting to Static Analysis service")
    appscan_login(os.environ.get('APPSCAN_USER_ID'),os.environ.get('APPSCAN_USER_TOKEN'))

    # if the job we would run is already up (and either pending or complete),
    # we just want to get state (and wait for it if needed), not create a whole
    # new submission
    python_utils.LOGGER.info("Scanning for code submission")
    files_to_submit = appscan_prepare()
    python_utils.LOGGER.info("Submitting scans for analysis")
    joblist, errMsg = appscan_submit(files_to_submit)
    if (not joblist) or len(joblist) < len(files_to_submit):
        if (not errMsg):
            errMsg = "Check status of existing scans."
        #Error, we didn't return as many jobs as we should have
        dash = os.environ.get('APPSCAN_SERVER_URL')
        if os.path.isfile("%s/utilities/sendMessage.sh" % python_utils.EXT_DIR):
            command='{path}/utilities/sendMessage.sh -l bad -m \"<{url}|Static security scan> could not successfully submit scan.  {errMsg}\"'.format(path=python_utils.EXT_DIR,url=dash,errMsg=errMsg)
            proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate();
            python_utils.LOGGER.debug(out)
        python_utils.LOGGER.error('ERROR: could not successfully submit scan. {errMsg} {url}'.format(url=dash,errMsg=errMsg))
        endtime = timeit.default_timer()
        print "Script completed in " + str(endtime - python_utils.SCRIPT_START_TIME) + " seconds"
        sys.exit(4)
    python_utils.LOGGER.info("Waiting for analysis to complete")

    # check on pending jobs, waiting if appropriate
    all_jobs_complete, high_issue_count, med_issue_count = wait_for_scans(joblist)

    # if we didn't successfully complete jobs, return that we timed out
    if not all_jobs_complete:
        # send slack notification 
        if os.path.isfile("%s/utilities/sendMessage.sh" % python_utils.EXT_DIR):
            dash = os.environ.get('APPSCAN_SERVER_URL')
            command='{path}/utilities/sendMessage.sh -l bad -m \"<{url}|Static security scan> did not complete within {wait} minutes.  Stage will need to be re-run after the scan completes.\"'.format(path=python_utils.EXT_DIR,url=dash,wait=python_utils.FULL_WAIT_TIME)
            proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate();
            python_utils.LOGGER.debug(out)

        endtime = timeit.default_timer()
        print "Script completed in " + str(endtime - python_utils.SCRIPT_START_TIME) + " seconds"
        sys.exit(2)
    else:
        if high_issue_count > 0:
            # send slack notification 
            if os.path.isfile("%s/utilities/sendMessage.sh" % python_utils.EXT_DIR):
                dash = os.environ.get('APPSCAN_SERVER_URL')
                command='{path}/utilities/sendMessage.sh -l bad -m \"<{url}|Static security scan> completed with {issues} high issues detected in the application.\"'.format(path=python_utils.EXT_DIR,url=dash, issues=high_issue_count)
                proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
                out, err = proc.communicate();
                python_utils.LOGGER.debug(out)
            
            endtime = timeit.default_timer()
            print "Script completed in " + str(endtime - python_utils.SCRIPT_START_TIME) + " seconds"
            sys.exit(3)

        if os.path.isfile("%s/utilities/sendMessage.sh" % python_utils.EXT_DIR):
            if med_issue_count > 0: 
                dash = os.environ.get('APPSCAN_SERVER_URL')
                command='SLACK_COLOR=\"warning\" {path}/utilities/sendMessage.sh -l good -m \"<{url}|Static security scan> completed with no major issues.\"'.format(path=python_utils.EXT_DIR,url=dash)
                proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
                out, err = proc.communicate();
                python_utils.LOGGER.debug(out)
            else:            
                dash = os.environ.get('APPSCAN_SERVER_URL')
                command='{path}/utilities/sendMessage.sh -l good -m \"<{url}|Static security scan> completed with no major issues.\"'.format(path=python_utils.EXT_DIR,url=dash)
                proc = Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
                out, err = proc.communicate();
                python_utils.LOGGER.debug(out)
        endtime = timeit.default_timer()
        print "Script completed in " + str(endtime - python_utils.SCRIPT_START_TIME) + " seconds"
        sys.exit(0)


except Exception, e:
    python_utils.LOGGER.warning("Exception received", exc_info=e)
    endtime = timeit.default_timer()
    print "Script completed in " + str(endtime - python_utils.SCRIPT_START_TIME) + " seconds"
    sys.exit(1)
