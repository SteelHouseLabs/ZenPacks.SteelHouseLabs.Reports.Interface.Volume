import time
import Globals
from Products.ZenReports import Utils, Utilization

import logging
log = logging.getLogger('zen.Reporting')

import re

def getRRDValues(component, dsNames, start=None, end=None, function=None, operation=None):
    result = {}
    gopts = []
    if not start:
        start = time.time() - component.defaultDateRange
    if not end:
        end = 'now'
    try:
        for dsName in dsNames:
            dpName = dsName + '_' + dsName
            dpObj = component.getRRDDataPoint(dpName)
            dpFile = component.getRRDFileName(dpName)
            gopts.append('DEF:%sDef=%s:ds0:AVERAGE' % (dsName, dpFile))
            gopts.append('CDEF:%sCDef=%sDef,0,INF,LIMIT' % (dsName, dsName))
            gopts.append('VDEF:%sAve=%sCDef,AVERAGE' % (dsName, dsName))
            if operation == 'TOTAL':
                gopts.append('CDEF:%sCond=%sCDef,UN,%sAve,%sCDef,IF' % (dsName, dsName, dsName, dsName))
                gopts.append('VDEF:%sTotal=%sCond,TOTAL' % (dsName, dsName))
                gopts.append('PRINT:%sTotal:%%.2lf' % (dsName))
            elif operation == 'AVERAGE':
                gopts.append('PRINT:%sAve:%%.2lf' % (dsName))
            gopts.append('--start=%d' % start)
            gopts.append('--end=%d' % end)
        rrdResult = component.device().getPerformanceServer().performanceCustomSummary(gopts)
        if rrdResult:
            for entry, dsName in enumerate(dsNames):
                result[dsName] = float(rrdResult[entry])
    except:
        log.debug('Something went wrong!')
        pass
    log.debug(str(result))
    return result

class interface_volume:
    'Interface volume performance report'

    def run(self, dmd, args):
        summary = Utilization.getSummaryArgs(dmd, args)
        deviceClass = args.get('deviceClass', '/Server')
        organizer = deviceClass
        showAll = args.get('showAll', '') == "on"
        deviceFilter = args.get('deviceFilter', '')
        deviceMatch = re.compile('.*%s.*' % deviceFilter)

        report = []
        if deviceClass == '/': return []

        parts = organizer.lstrip('/').split('/')
        try:
            if not len(parts):
                raise AttributeError() # Invalid organizer
            root = dmd.getDmdRoot(parts[0])
            for part in parts[1:]:
                root = getattr(root, part)
        except AttributeError:
            root = dmd.Devices

        for org in [root,] + root.getSubOrganizers():
            path = org.getPrimaryUrlPath()
            for devObj in org.getDevices():
                devObj = devObj.primaryAq()
                if not deviceMatch.match(devObj.id): continue
                types = getattr(org, 'zPerfReportableMetaTypes', ['IpInterface'])
                avePeriod = getattr(org, 'zPerfReportableAvePeriod', 86400)
                fullComponentList = []
                for typeEntry in types:
                    fullComponentList = fullComponentList + devObj.getMonitoredComponents(type=str(typeEntry))
                for intObj in fullComponentList:
                    if not showAll:
                        if intObj.snmpIgnore(): continue
                        isLocal = re.compile(devObj.zLocalInterfaceNames)
                        if isLocal.match(intObj.name()): continue
                        if not intObj.speed:
                            speed = 'Unknown'
                        else:
                            speed = intObj.speed

                        counters = ['ifHCInOctets', 'ifHCOutOctets', 'ifInOctets', 'ifOutOctets']

                        def multiply(number, by):
                            if number is None or by is None:
                                return None
                            return number * by

                        aveVals = getRRDValues(intObj, dsNames=counters, operation='AVERAGE', **summary)
                        volAveIn = multiply(aveVals.get('ifHCInOctets', aveVals.get('ifInOctets', None)), avePeriod)
                        volAveOut = multiply(aveVals.get('ifHCOutOctets', aveVals.get('ifOutOctets', None)), avePeriod)

                        totalVals = getRRDValues(intObj, counters, operation='TOTAL', **summary)
                        volIn = totalVals.get('ifHCInOctets', totalVals.get('ifInOctets', None))
                        volOut = totalVals.get('ifHCOutOctets', totalVals.get('ifOutOctets', None))

                        if volAveOut and volAveIn:
                            volTotal = volOut + volIn
                        else:
                            volTotal = 0

                        record = Utils.Record(device = devObj.id,
                            devicePath = devObj.getPrimaryUrlPath(),
                            id = intObj.id,
                            path = intObj.getPrimaryUrlPath(),
                            description = intObj.description,
                            speed = speed,
                            volIn = volIn,
                            volOut = volOut,
                            volAveIn = volAveIn,
                            volAveOut = volAveOut,
                            volTotal = volTotal)
                        report.append(record)
        return report