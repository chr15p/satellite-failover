#!/usr/bin/python
from datetime import datetime
from optparse import OptionParser
from ConfigParser import SafeConfigParser

import yaml
import subprocess
import re


error_colors = {
    'HEADER': '\033[95m',
    'OKBLUE': '\033[94m',
    'OKGREEN': '\033[92m',
    'WARNING': '\033[93m',
    'FAIL': '\033[91m',
    'ENDC': '\033[0m',
}

def print_error(msg):
    print "[%sERROR%s], [%s], EXITING: [%s] failed to execute properly." % (error_colors['FAIL'], error_colors['ENDC'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
    exit(1)

def print_warning(msg):
    print "[%sWARNING%s], [%s], NON-FATAL: [%s] failed to execute properly." % (error_colors['WARNING'], error_colors['ENDC'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)


def print_success(msg):
    print "[%sSUCCESS%s], [%s], [%s], completed successfully." % (error_colors['OKGREEN'], error_colors['ENDC'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)


def print_running(msg):
    print "[%sRUNNING%s], [%s], [%s] " % (error_colors['OKBLUE'], error_colors['ENDC'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)


def print_generic(msg):
    print "[NOTIFICATION], [%s], [%s] " % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)


def exec_failok(command):
    print_running(command)
    output = ""
    try:
        output = subprocess.check_output(command)
    except Exception,e:
        print_warning("command \'%s\' failed: %s"%(command,e))

    return output


def exec_failexit(command):
    print_running(command)
    output = ""
    try:
        output = subprocess.check_output(command)
    except Exception,e:
        print_generic(output)
        print_error("command \'%s\' failed: %s"%(command,e))
    return output



class Failoverset:
    def __init__(self, configfile):
        print_generic("Attempting to parse failover config")
        self.defaults=dict()
        self.capsules=dict()
        with open(configfile, 'r') as stream:
            try:
                cfg=yaml.load(stream)
                cfg.get('failover')
            except yaml.YAMLError as exc:
                print_error("unable to read %s: %s"%(configfile,exc))
        
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
            print_warning("failed to get current capsule %s"%e)
    
        return hostname


    def getnextcapsule(self):
        nextcapsule = "" 
        for i in self.capsules.keys():
            if self.capsules[i].hostname == self.currenthostname:
                next
            elif nextcapsule == "" or ( self.capsules[i].priority > self.capsules[nextcapsule].priority):
                nextcapsule=i
        return nextcapsule


    def failover(self):
        nextcapsule = self.getnextcapsule()
        print_generic("failing over to %s"%nextcapsule)
        self.capsules[nextcapsule].failover()
	


class Capsule:
    def __init__(self,config,configdir):
        if config.get("name") == None:
            print_error("name attribute is required")
            exit(1)

        self.hostname = config.get("hostname",config.get("name"))
        self.priority = config.get("priority",1)
        self.configdir = config.get("configdir", configdir + "/" + self.hostname )
        self.puppetmaster = config.get("puppetmaster",config.get("name"))
        self.puppetca = config.get("puppetca",self.puppetmaster)
        self.services = config.get("services",{})
        for s in self.services.keys():
            if self.services[s]== False:
                del self.services[s]

        if self.services == {}:
            print_error("no services defined for %s"%self.hostname)


    def failover(self):
        ## list services in order they need to be failed over
        for s in ['pulp','gopher','puppetca','puppet']:
            try:
                self.getattr("failover_%s"%s)(self.services[s])
            except AttributeError,e:
                print_warning("failover for %s not supported: %s"%(s,e))            


    def failover_pulp(self,arg):
        consumer = [self.configdir + "/katello-rhsm-consumer"]
        #print_running(consumer)
        exec_failexit(consumer)

        clean=["/usr/bin/yum","clean","all"]
        #print_running(clean)
        exec_failexit(clean)


    def failover_gofer(self,arg):
        gofer=["systemctl","restart","goferd"]
        #print_running(gofer)
        exec_failexit(gofer)
    

    def failover_puppetca(self,arg):
	caserver = ["puppet","config","set", "--section", "agent", "ca_server", self.puppetca]
        exec_failexit(caserver)

    
    def failover_puppet(self,arg):
	server = ["puppet","config","set","--section","agent", "server", self.puppetmaster]
        exec_failexit(server)
	puppet = ["systemctl","restart","puppet"]
        exec_failexit(puppet)





if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="failover_config", help="Custom path to failover config yaml file", metavar="failover_config", default="/etc/satellite-failover.cfg")
    (opt,args) = parser.parse_args()
    #main()

    fs=Failoverset(opt.failover_config)
    fs.failover()

