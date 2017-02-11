#!/usr/bin/python
from datetime import datetime
from optparse import OptionParser
from ConfigParser import SafeConfigParser

import yaml
import subprocess
import re
import os.path
import random
import pprint

error_colors = {
	'HEADER': '\033[95m',
	'OK': '\033[92m',
	'GENERIC': '\033[94m',
	'WARNING': '\033[93m',
	'ERROR': '\033[91m',
	'FATAL': '\033[91m',
	'ENDC': '\033[0m',
}

def logger(level,msg):
	level=level.upper()
	print "[%s%s%s], [%s]: [%s]" % (error_colors[level],level,error_colors['ENDC'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
	if level=="FATAL":
		exit(1)



def exec_failok(command):
	print_running(command)
	output = ""
	try:
		output = subprocess.check_output(command)
	except Exception,e:
		#print_warning("command \'%s\' failed: %s"%(command,e))
		logger("warning","command \'%s\' failed: %s"%(command,e))

	return output


def exec_failexit(command):
	print_running(command)
	output = ""
	try:
		output = subprocess.check_output(command)
	except Exception,e:
		#print_generic(output)
		#print_error("command \'%s\' failed: %s"%(command,e))
		logger("fatal","command \'%s\' failed: %s"%(command,e))
	return output


def readfile(configfile):
        serviceset = {}
        logger("generic","Attempting to parse failover config")
        #capsules=dict()
        allsets=[]
        with open(configfile, 'r') as stream:
                try:
                        yml=yaml.load(stream)
                        allsets = yml.get('failover')
                except yaml.YAMLError as exc:
                        #print_error("unable to read %s: %s"%(configfile,exc))
                        logger("fatal","unable to read %s: %s"%(configfile,exc))
        
        #pprint.pprint(allsets)
        #exit()
        i=0
        for s in allsets:
                capsules=dict()
                services=dict()

                i=i+1
                try:
                        name = s["name"]
                except KeyError,e:
                        name = str(i)

                try:
                        configdir = s["configdir"]
                except KeyError,e:
                        configdir = "/usr/lofi/%s"%name

                serviceset[name] = ServiceSet() #{"capsules": [],"services":{}}

                try:
                        services = s["services"]
                except KeyError,e:
                        logger("warning","no services defined for %s, defaulting to pulp")
                        services = {"pulp":"/etc/rhsm/rhsm.conf"} 

                try:
                        capsules = s["capsules"]
                except KeyError,e:
                        logger("fatal","no capsules defined for %s exiting.")

                for v in services.keys():
                        if v== "puppet":
                                #serviceset[name]['services']['puppet']=Puppet(services['puppet'])
                                serviceset[name].addservice('puppet',Puppet(services['puppet']))
                        elif v == "pulp":
                                #serviceset[name]['services']['pulp']=Pulp(services['pulp'])
                                serviceset[name].addservice('pulp',Puppet(services['pulp']))
                        else:
                                logger("fatal","service %s not supported"%v)

                for c in capsules:
                        #print c
                        cfg=dict()
                        cfg['name']=c.get("name",False)
                        cfg['cfgdir']=configdir
                        cfg['hostname']=c.get('hostname',cfg['name'])
                        cfg['priority']=c.get('priority',1)
                        #serviceset[name]['capsules'].append(Capsule(cfg))
                        serviceset[name].addcapsule(cfg['name'],Capsule(cfg))
        #print "#######################"
        #pprint.pprint(serviceset)

        return serviceset




class ServiceSet:
	def __init__(self):
                self.services=dict()
                self.capsules=dict()
                self._currentcapsule = None
		#self._config = self.readfile(configfile)
		#self._currentcapsules = self.getcurrentcapsule()
		#print self._currentcapsules	
		#print self.getnextcapsule('default').pulp
		#for i in self.services.keys():
		#	i.failover(self.capsules[self.currenthostname]

        def addservice(self,name,obj):
                self.services[name]=obj

        def addcapsule(self,name,obj):
                self.capsules[name]=obj

	def _getcurrentpuppetmaster(self):
		pm = subprocess.Popen(["puppet","config","print","--section","agent","server"],stdout=subprocess.PIPE)
		puppetmaster = pm.stdout.readline().rstrip()
		#print "x=%s"%puppetmaster
		return puppetmaster


	def _getcurrentpulp(self):
		hostname=None
		try:
			proc = subprocess.Popen(['subscription-manager','config','--list'],stdout=subprocess.PIPE)
			for line in proc.stdout.readlines():
				#print "line=%s"%line
				m=re.match(r" *hostname *= *\[?([\.\w-]+)\]?",line)
				if m:
					hostname = m.group(1)
					#print "y=%s"%hostname
					return hostname
		except Exception,e:
			#print_warning("failed to get current capsule %s"%e)
			logger("warning","failed to get current capsule %s"%e)

		return hostname	


	def getcurrentcapsule(self):
                if self._currentcapsule == None:
        		current=dict()
	        	hostname = self._getcurrentpulp()
	        	puppetmaster = self._getcurrentpuppetmaster()
	        	#print "pulp=%s+ puppetmaster=%s+"%(hostname,puppetmaster)
			for i in self.capsules.keys():
			        #print "ipulp=%s+ ipuppetmaster=%s+"%(i.pulp,i.puppetmaster)
        			#print "=pulp=%s =puppetmaster=%s"%(i.pulp==hostname,i.puppetmaster==puppetmaster)
	        		if self.capsules[i].hostname == puppetmaster and self.capsues[i].hostname == hostname:
                                        self._currentcapsule = self.capsules[i]
                                        break
                        
		return self._currentcapsule 


	def getnextcapsule(self,blacklist=[]):
                ### get the next capsule from a single set called name
		nextcapsule = []
		nextprio=-1
                #print "########"
                #pprint.pprint(self._config['default'])
                #print "========########"
		for i in self.capsules.keys():
			#if i == self._currentcapsules[name]:
			if i in blacklist:
				##skip if its the current capsule so we cant fail onto it
				next
			elif nextcapsule == "" or ( self.capsules[i].priority == nextprio):
				##TODO test if this capsule is actually up....
				nextcapsule.append(self.casules[i])
			elif self.capsules[i].priority > nextprio:
				nextcapsule = []
				nextcapsule.append(self.capsules[i])
				nextprio=self.capsules[i].priority
		
		if len(nextcapsule)== 1:
			return nextcapsule[0]
		elif len(nextcapsule)== 0:
			raise Exception("unable to find a valid capsule to failover to")
			return False
		else:
			## we have multiple options pick a random one...
			return nextcapsule[random.randint(0,len(nextcapsule))]


	def failover(self):
                ##failover to a single named set
		nextcapsule = self.getnextcapsule([self.getcurrentcapsule()])
                #print nextcapsule
		if nextcapsule == False:
			logger("fatal","no valid capsules remaining")
	#	#print_generic("failing over to %s"%nextcapsule)
		logger("ok","failing over to '%s'"%nextcapsule.name)
                for s in self.services.keys():
                    try:
                        self.services[s].failover(nextcapsule)
                    except:
                        logger("error","failed to failover %s to %s"%(s,nextcapsule.name()))
	#	self.capsules[nextcapsule].state("failover",self.currenthostname)
	



class Capsule:
	def __init__(self,config):
		self._name=config['name']
		self._priority=config['priority']
		self._hostname=config.get('hostname',False)

	@property
	def name(self):
		return self._name

	@property
	def priority(self):
		return self._priority

	@property
	def hostname(self):
		return self._hostname

	def _getcurrentpuppetmaster(self):
		pm = subprocess.Popen(["puppet","config","print","--section","agent","server"],stdout=subprocess.PIPE)
		puppetmaster = pm.stdout.readline().rstrip()
		#print "x=%s"%puppetmaster
		return puppetmaster

	#def test(self):
	#	if not self.testpulp():
	#		return False
	#	if not self.testpuppet():
	#		return False
	#	return True
        #
        #
	#def testpuppet(self):
	#	## if not configured then pass automatically
	#	if self._puppetmaster == False:
	#		return True
	#	proc = subprocess.Popen(["/usr/bin/puppet","status","find","test","--terminus","rest","--server", self._puppetmaster])
	#	return 0
        #
	#def testpulp():
	#	## if not configured then pass automatically
	#	if self._pulp == False:
	#		return True
	#	return 0


class Service():
	def __init__(self,configfile):
		self._file=configfile

	@property
	def file(self):
		return self._file

	def failover(self,to):
		pass

        def test(self,oncapsule):
                pass
    

class Pulp(Service):
	def failover(self,arg):
                return 0
		consumer = [self.configdir + "/katello-rhsm-consumer"]
		#print_running(consumer)
		exec_failexit(consumer)

		clean=["/usr/bin/yum","clean","all"]
		#print_running(clean)
		exec_failexit(clean)
		submanager=["subscription-manager","refresh"]
		exec_failexit(submanager)
		gofer=["systemctl","restart","goferd"]
		#print_running(gofer)
		exec_failexit(gofer)
		return 0
	

class Puppet(Service):
	
	def failover(self,currhost):
                return 0
		try:
			currpuppetmaster = exec_failok(["/usr/bin/puppet","config"," print","--section","agent","ca_server"])	
		except:
			currpuppetmaster = currhost

		exec_failexit(["mv","/var/lib/puppet/ssl","/var/lib/puppet/ssl-" + currpuppetmaster])
		if os.path.isdir("/var/lib/puppet/ssl-%s"%self.puppetmaster):
			exec_failexit(["mv","/var/lib/puppet/ssl-" + self.puppetca,"/var/lib/puppet/ssl"])

		exec_failexit(["/usr/bin/puppet","config","set","--section","agent","server", self.puppetmaster])
		exec_failexit(["/usr/bin/puppet","config","set","--section","agent","ca_server", self.puppetca])
		exec_failexit(["/sbin/service","puppet","try-restart"])
		return 0

	def test(self,capsule):
		## if not configured then pass automatically
                puppetmaster = capsule.hostname
		if self._puppetmaster == False:
			return True
		proc = subprocess.Popen(["/usr/bin/puppet","status","find","test","--terminus","rest","--server", self._puppetmaster])
		return 0



if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("-c", "--config", dest="failover_config", help="Custom path to failover config yaml file", metavar="failover_config", default="/etc/satellite-failover.cfg")
	(opt,args) = parser.parse_args()
	#main()

        sets=readfile(opt.failover_config)
        for i in sets.keys():
            sets[i].failover()
	#fs=CapsuleSet(opt.failover_config)
        #for i in fs.sets:
        #        #print "i=%s"%i
        #	fs.failover(i)

