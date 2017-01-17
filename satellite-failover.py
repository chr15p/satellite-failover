#!/usr/bin/python
from datetime import datetime
from optparse import OptionParser
from ConfigParser import SafeConfigParser

import yaml
import subprocess
import re
import os.path


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
	level=ucase(level)
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



class Failoverset:
	def __init__(self, configfile):
		#print_generic("Attempting to parse failover config")
		logger("generic","Attempting to parse failover config")
		self.defaults=dict()
		self.capsules=dict()
		with open(configfile, 'r') as stream:
			try:
				cfg=yaml.load(stream)
				cfg.get('failover')
			except yaml.YAMLError as exc:
				#print_error("unable to read %s: %s"%(configfile,exc))
				logger("fatal","unable to read %s: %s"%(configfile,exc))
		
		for key in ["configdir","log"]:
			if cfg['failover'].get(key):
				self.defaults[key] = cfg['failover'][key]
		
		#print self.defaults
		for i in cfg['failover']['capsules']:
			cap = Capsule(i,self.defaults['configdir'])
			self.capsules[cap.hostname] = cap
			#print_error("capsule without name in %s"%(configfile))

		self.currenthostname = self.getcurrentcapsule()


	def getcurrentcapsule(self):
		hostname=None
		try:
			proc = subprocess.Popen(['subscription-manager','config','--list'],stdout=subprocess.PIPE)
			for line in proc.stdout.readlines():
				#print "line=%s"%line
				m=re.match(r" *hostname *= *\[?([\.\w-]+)\]?",line)
				if m:
					hostname = m.group(1)
					break
		except Exception,e:
			#print_warning("failed to get current capsule %s"%e)
			logger("warning","failed to get current capsule %s"%e)
	
		return hostname


	def getnextcapsule(self):
		nextcapsule = "" 
		for i in self.capsules.keys():
			if self.capsules[i].hostname == self.currenthostname:
				next
			elif nextcapsule == "" or ( self.capsules[i].priority > self.capsules[nextcapsule].priority):
				##TODO test if this capsule is actually up....
				nextcapsule=i
		return nextcapsule


	def failover(self):
		nextcapsule = self.getnextcapsule()
		if nextcapsule == "": 
			#print_error("no valid capsules remaining")
			logger("fatal","no valid capsules remaining")
		#print_generic("failing over to %s"%nextcapsule)
		logger("ok","failing over to %s"%nextcapsule)
		self.capsules[nextcapsule].state("failover",self.currenthostname)
	




class Capsule:
	def __init__(self,config,configdir):
		if config.get("name") == None:
			#print_error("name attribute is required")
			logger("fatal","name attribute is required")
			exit(1)

		self.hostname = config.get("hostname",config.get("name"))
		self.priority = config.get("priority",1)
		self.configdir = config.get("configdir", configdir + "/" + self.hostname )
		self.puppetmaster = config.get("puppetmaster",self.hostname)
		self.puppetca = config.get("puppetca",self.puppetmaster)
		self.services = config.get("services",{"puppet","pulp"})
		for s in self.services.keys():
			if self.services[s]== False:
				del self.services[s]

		if self.services == {}:
			#print_error("no services defined for %s"%self.hostname)
			logger("fatal","no services defined for %s"%self.hostname)


	def state(self,state,currenthost):
		result=0
		## list services in order they need to be failed over
		for s in ['pulp','gofer','puppet']:
			if self.services.get(s):
				print "%s_%s"%(state,s)
				print self.services[s]
				try:
					#result = result + getattr(self,"%s_%s"%(state,s))(self.services[s], currenthost)
					result = result + getattr(self,"%s_%s"%(state,s))(currenthost)
				except AttributeError,e:
					#print_warning("%s for %s not supported: %s"%(state,s,e))			
					logger("warning","%s for %s not supported: %s"%(state,s,e))			
		return result


	def failover_pulp(self,arg):
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
	

	#def failover_puppetca(self,arg):
	#	caserver = ["puppet","config","set", "--section", "agent", "ca_server", self.puppetca]
	#	exec_failexit(caserver)

	
	def failover_puppet(self,currhost):
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


	#def test_puppet(self):
	#	proc = subprocess.Popen(["/usr/bin/puppet","status","find","test","--terminus","rest","--server", self.puppetmaster])
	#	return 0

	#def test_pulp():
	#	return 0



if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("-c", "--config", dest="failover_config", help="Custom path to failover config yaml file", metavar="failover_config", default="/etc/satellite-failover.cfg")
	(opt,args) = parser.parse_args()
	#main()

	fs=Failoverset(opt.failover_config)
	fs.failover()

