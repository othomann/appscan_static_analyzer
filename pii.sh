###############################################################################
# Licensed Materials - Property of IBM
# (c) Copyright IBM Corporation 2015, 2017. All Rights Reserved.
#
# Note to U.S. Government Users Restricted Rights:
# Use, duplication or disclosure restricted by GSA ADP Schedule
# Contract with IBM Corp.
###############################################################################
#!/bin/bash -x
if [[ ! -e archive ]]; then
	mkdir archive
fi

# copy all message files (except translations) into archive, following the same folder structure
find . -type f | egrep -i "/[^_]+\.properties$" | xargs -J % rsync -Rv % archive

# Recursively check all files being sent for translation
# See: https://github.w3ibm.bluemix.net/org-ids/otc-deploy/blob/master/tools/README.md
~/tools/chkpii "archive/*" -OS -S

cd archive
zip appscan_static_analyzer.zip -r .
