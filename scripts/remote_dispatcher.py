import subprocess
import sh
import select
import time
import pdb


class RemoteServer(object):
    def __init__(self, server_name, interface, launch_job = True):
        self.server_name = server_name
        self.kill_previous()
        self.filename = open("/dev/null","rw")
        if launch_job:
            self.subprocess = self.launch_job()
        self.interface = interface
        self.killed_forcibly = False

    def launch_job(self):
        args = ["ssh", self.server_name, "python", "/home/jweisz/gm/graspit_dispatcher.py"]
        print "%s \n"%(self.server_name)
        return subprocess.Popen(args, stdin = subprocess.PIPE, stdout=self.filename, stderr=subprocess.STDOUT)

    def kill_if_busy(self):       
        args = ["ssh", self.server_name, "python", "/home/jweisz/gm/graspit_dispatch_monitor.py"]
        print "%s \n"%(self.server_name)
        return subprocess.Popen(args, stdin = subprocess.PIPE, stdout=self.filename, stderr=subprocess.STDOUT)

    def kill_previous(self):
        args = ["ssh", self.server_name, "killall", "python"]
        s = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        s.communicate()
        args = ["ssh", self.server_name, "killall", "graspit"]
        s = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        s.communicate()

        
    def is_running(self):
        #self.process_output()
        return self.subprocess.poll() == None


    def mark_failed_task(self):
        t = ''
        try:
            if not select.select([self.subprocess.stdout],[],[],0)[0]:
                return t
            t = self.subprocess.stdout.readline()            
            line_list = t.split(' ')            
            job_id_index = line_list.index('unfinished') - 1
            job_id = int(line_list[job_id_index])
            print t
            self.interface.set_task_outcome_id(job_id, 1)
        except:
            pass
        return t

    def process_output(self):
        while self.mark_failed_task() != '':
            continue
                
            


class RemoteDispatcher(object):
    def __init__(self, server_name_dict, interface):
        self.server_dict = dict()
        self.interface = interface
        for server in server_name_dict:
            try:
                a = sh.ping(server,w=1)
            except:
                print "Couldn't ping %s"%(server)
                continue
            if a.exit_code:
                print "Couldn't ping %s"%(server)
                continue
            print "pinged %s"%(server)                
            self.server_dict[server] = RemoteServer(server, interface)

        self.file = open('/tmp/running_jobs.txt','w')

    def run(self):
        running = 1
            
        while running:            
            running = len([server for server in self.server_dict.values() if server.is_running()])
            self.file.seek(0)
            self.file.write('Running processes %i %s \n'%(running, time.strftime('%c')))
            self.file.flush()
            time.sleep(1)
            
    
    def run_monitored(self, monitor_functor = []):
        running = 1
        while running:
            for server in self.server_dict.values():                
                if server.kill_if_busy():
                    server.killed_forcibly = True
                    server.kill_previous()
                    server.subprocess.kill()
                    #This is where you would report busyness if necessary
                    #This is where you would generate an update to any reported statistics if necessary
            running = len([server for server in self.server_dict.values() if server.is_running()])
            if monitor_functor:
                monitor_functor(self.server_dict)
