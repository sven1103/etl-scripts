'''

Note:
print statements go to: ~openbis/servers/datastore_server/log/startup_log.txt
'''
import sys
sys.path.append('/home-link/qeana10/bin/')

import checksum
import re
import os
import ch.systemsx.cisd.etlserver.registrator.api.v2
from java.io import File
from org.apache.commons.io import FileUtils
from ch.systemsx.cisd.openbis.generic.shared.api.v1.dto import SearchCriteria
from ch.systemsx.cisd.openbis.generic.shared.api.v1.dto import SearchSubCriteria

# ETL script for registration of VCF files
# expected:
# *Q[Project Code]^4[Sample No.]^3[Sample Type][Checksum]*.*
pattern = re.compile('Q\w{4}[0-9]{3}[a-zA-Z]\w')

def isExpected(identifier):
        try:
                id = identifier[0:9]
                #also checks for old checksums with lower case letters
                return checksum.checksum(id)==identifier[9]
        except:
                return False

def process(transaction):
        context = transaction.getRegistrationContext().getPersistentMap()

        # Get the incoming path of the transaction
        incomingPath = transaction.getIncoming().getAbsolutePath()

        key = context.get("RETRY_COUNT")
        if (key == None):
                key = 1


        # Get the name of the incoming file
        name = transaction.getIncoming().getName()
        
        identifier = pattern.findall(name)[0]
        if isExpected(identifier):
                project = identifier[:5]
                parentCode = identifier[:10]
        else:
                print "The identifier "+identifier+" did not match the pattern Q[A-Z]{4}\d{3}\w{2} or checksum"
        
        search_service = transaction.getSearchService()
        sc = SearchCriteria()
        sc.addMatchClause(SearchCriteria.MatchClause.createAttributeMatch(SearchCriteria.MatchClauseAttribute.CODE, identifier))
        foundSamples = search_service.searchForSamples(sc)

        parentSampleIdentifier = foundSamples[0].getSampleIdentifier()
        space = foundSamples[0].getSpace()
        sa = transaction.getSampleForUpdate(parentSampleIdentifier)
        # find or register new experiment
        expType = "Q_MS_MEASUREMENT"
        msExperiment = None
        experiments = search_service.listExperiments("/" + space + "/" + project)
        experimentIDs = []
        for exp in experiments:
                experimentIDs.append(exp.getExperimentIdentifier())
                if exp.getExperimentType() == expType:
                        msExperiment = exp
        # no existing experiment for samples of this sample preparation found
        if not msExperiment:
                expID = experimentIDs[0]
                i = 0
                while expID in experimentIDs:
                        i += 1
                        expNum = len(experiments) + i
                        expID = '/' + space + '/' + project + '/' + project + 'E' + str(expNum)
                msExperiment = transaction.createNewExperiment(expID, expType)

        newMSSample = transaction.createNewSample('/' + space + '/' + 'MS'+ parentCode, "Q_MS_RUN")
        newMSSample.setParentSampleIdentifiers([sa.getSampleIdentifier()])
        newMSSample.setExperiment(msExperiment) 
        # create new dataset 
        dataSet = transaction.createNewDataSet("Q_MS_MZML_DATA")
        dataSet.setMeasuredData(False)
        dataSet.setSample(newMSSample)

        transaction.moveFile(incomingPath, dataSet)