import subprocess
import sh
import select
import time
import pdb
import threading
from ctypes import *

class RemoteServer(object):
    def __init__(self, server_name, interface):
        self.server_name = server_name
        self.subprocesses = []
        self.interface = interface
        self.killed_forcibly = False
        #self.kill_previous()

    def launch_job(self):
        with open('/dev/null','rw') as null_file:
            args = ["ssh", "-o","ConnectTimeout=30", self.server_name, "/home/jweisz/gm/run_dispatcher.sh"]
            print "%s \n"%(self.server_name)
            self.subprocesses.append(subprocess.Popen(args, stdin = subprocess.PIPE, stdout=null_file, stderr=subprocess.STDOUT))

    def kill_if_busy(self):
        with open('/dev/null','rw') as null_file:
            args = ["ssh", "-o","PasswordAuthentication=no", self.server_name, "python", "/home/jweisz/gm/graspit_dispatch_monitor.py"]
            print "%s \n"%(self.server_name)
            return subprocess.Popen(args, stdin = subprocess.PIPE, stdout=null_file, stderr=subprocess.STDOUT)

    def kill_previous(self):
        args = ["ssh", "-o","PasswordAuthentication=no", "-o","ConnectTimeout=30",self.server_name, "killall", "python"]
        self.subprocesses.append(subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
            
        args = ["ssh", "-o","PasswordAuthentication=no", "-o","ConnectTimeout=30", self.server_name, "killall", "graspit"]
        self.subprocesses.append(subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))

    def do_all(self):        
        args = ["ssh", "-o","ConnectTimeout=30",self.server_name, "killall", "python;", "killall","graspit;","killall","nice;", "/home/jweisz/gm/run_dispatcher.sh"]
        self.subprocesses.append(subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))

    def collect_subprocesses(self):
        for s in self.subprocesses:
            s.communicate()
        self.subprocesses = []
        
    def is_running(self):
        #self.process_output()        
        return self.subprocesses[0].poll() == None


    def mark_failed_task(self):
        t = ''
        try:
            if not select.select([self.subprocesses[0].stdout],[],[],0)[0]:
                return t
            t = self.subprocesses[0].stdout.readline()            
            line_list = t.split(' ')            
            job_id_index = line_list.index('unfinished') - 1
            job_id = int(line_list[job_id_index])
            print t
            self.interface.set_task_outcome_id(job_id, 1)
        except:
            pass
        return t

    def kill_all_subprocesses(self):
        for s in self.subprocesses:
            try:
                s.kill()
            except:
                pass
            
    def process_output(self):
        while self.mark_failed_task() != '':
            continue
                
           

import pdb
class RemoteDispatcher(object):
    def __init__(self, server_name_dict, interface):
        self.server_dict = dict()
        self.server_starting_dict = dict()
        self.interface = interface
        self.thread_list = []
        print "server name dict"
        print server_name_dict.keys()
        for server in server_name_dict:
            self.thread_list.append(threading.Thread(target = self.init_server, args=(server,)))
            self.thread_list[-1].start()
        print "waiting for threads to join"
        #for thread in thread_list:
        #    thread.join()
        print "Threads joined"
        
        self.file = open('/var/www/eigenhand_project/running_jobs.shtml','w')

    def init_server(self, server_name):
        """
        try:
            a = sh.ping(server_name,w=1)
        except:
            print "Couldn't ping %s"%(server_name)
            return
        if a.exit_code:
            print "Couldn't ping %s"%(server_name)
            return
        print "pinged %s"%(server_name)
        """
        try:
            a = RemoteServer(server_name, self.interface)
            self.server_starting_dict[server_name] = a
            #a.kill_previous()
            #self.start_server(a)
            a.do_all()
            self.server_dict[server_name] = a
        except:
            print "server :%s failed to start"%(server_name)
        

    def start_server(self, server):
        server.collect_subprocesses()
        server.launch_job()
            
    def run(self, max_len = 9800):
        running = 1
        t = time.time()
        generation = self.interface.get_max_hand_gen()
        self.file.write('started running generation %i at %s \n'%(generation,time.strftime('%c')))
        self.file.seek(0)
        self.file.flush()
        time.sleep(120)
        running_servers = []
        while running and self.interface.get_num_incompletes() > 0 and time.time() - t < max_len and self.interface.get_num_running(60):
            test_dict = dict(self.server_dict)
            running_servers = [server for server in test_dict.values() if server.is_running()]
            nonrunning_servers = [server for server in test_dict.values() if server not in running_servers]
            if self.interface.get_num_runable(30):
                for server in nonrunning_servers:
                    print "restarting %s"%(server.server_name)
                    server.collect_subprocesses()
                    server.do_all()
            if self.server_dict.values() != []:
                running = len(running_servers)
            self.file.seek(0)
            self.file.write('Generation %i, Running processes %i jobs %i %s \n'%(generation, running, self.interface.get_num_incompletes(), time.strftime('%c')))
            self.file.write(' '.join([server.server_name for server in running_servers]) + '\n')
            self.file.truncate()
            self.file.flush()
            time.sleep(3)
        finished_string = 'Finished running generation %i. time taken %i num incompletes %i. time %s \n'%(self.interface.get_max_hand_gen(), time.time() - t,
                                                                                                 self.interface.get_num_incompletes(),
                                                                                                time.strftime('%c'))
        print finished_string
        if running_servers:
            print running_servers
        
        self.file.seek(0)
        self.file.write(finished_string)
        self.file.truncate()
        self.file.flush()
        self.file.close()
        for server in self.server_starting_dict.values():
            try:
                server.kill_all_subprocesses()
            except:
                pass
            del server
        
            
        #for thread in self.thread_list:
        #    if thread.is_alive():
        #        pthread = cdll.LoadLibrary("libpthread-2.10.1.so")
        #        pthread.pthread_cancel(c_ulong(thread.ident))
                
        
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
