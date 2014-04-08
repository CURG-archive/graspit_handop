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
        self.subprocess = []
        self.interface = interface
        self.killed_forcibly = False
        self.restart_count = -1
        #self.kill_previous()

    def launch_job(self):
        with open('/dev/null','rw') as null_file:
            args = ["ssh", "-o","ConnectTimeout=30", self.server_name, "/home/jweisz/gm/run_dispatcher.sh"]
            print "%s \n"%(self.server_name)
            self.subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=null_file, stderr=subprocess.STDOUT)
            self.restart_count += 1


    def kill_if_busy(self):
        with open('/dev/null','rw') as null_file:
            args = ["ssh", "-o","PasswordAuthentication=no", self.server_name, "python", "/home/jweisz/gm/graspit_dispatch_monitor.py"]
            print "%s \n"%(self.server_name)
            return subprocess.Popen(args, stdin = subprocess.PIPE, stdout=null_file, stderr=subprocess.STDOUT)

    def kill_previous(self):
        args = ["ssh", "-o","PasswordAuthentication=no", "-o","ConnectTimeout=30",self.server_name, "killall", "python"]
        subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.communicate()

        self.subprocess.communicate()
            
        args = ["ssh", "-o","PasswordAuthentication=no", "-o","ConnectTimeout=30", self.server_name, "killall", "graspit"]
        subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.communicate()

    def do_all(self):        
        args = ["ssh", "-o","ConnectTimeout=30",self.server_name, "killall", "python;", "killall","graspit;","killall","nice;"]
        subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.communicate()

        self.subprocess.communicate()

        args = ["ssh", "-o","ConnectTimeout=30",self.server_name, "/home/jweisz/gm/run_dispatcher.sh"]
        self.subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.restart_count += 1

    def collect_subprocesses(self):
        """While it is theoretically possible to have more than one subprocess
        we never have a case where this occurs in the code"""
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
                
    def __str__(self):
        return ("%s: %s"%(self.server_name,"running" if self.is_running() else "dead"))

import pdb
class RemoteDispatcher(object):
    def __init__(self, interface):
        self.server_dict = dict()
        self.server_starting_dict = dict()
        self.interface = interface
        self.thread_list = []
        
        self.file = open('/var/www/eigenhand_project/running_jobs.shtml','w')

    def init_all_servers(self, server_name_dict):
        for server in server_name_dict:
            self.thread_list.append(threading.Thread(target = self.init_server, args=(server,)))
            self.thread_list[-1].start()
        print "waiting for threads to join"
        #for thread in thread_list:
        #    thread.join()
        print "Threads joined"

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
        
    def kill_all_servers(self):
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

        self.file.close()

    def start_server(self, server):
        server.collect_subprocesses()
        server.launch_job()
            
    def run(self, max_len = 9800):
        t = time.time()
        generation = self.interface.get_max_hand_gen()

        self.file.write('Started running generation %i at %s \n'%(generation,time.strftime('%c')))
        self.file.seek(0)
        self.file.flush()

        time.sleep(120)

        num_running = self.interface.get_num_running(60)
        while self.interface.get_num_incompletes() > 0 and time.time() - t < max_len and self.interface.get_num_running(60):

            nonrunning_server_data = self.interface.get_dead_servers(180)
            num_running = self.interface.get_num_running(60)
            for server_data in nonrunning_server_data:
                try:
                    print "Restarting %s (%s); Time: %s"%(server_data['server_name'],server_data['ip_addr'],time.strftime("%a, %b %d, %Y %H:%M:%S"))
                    server = self.server_dict[server_data['ip_addr']]
                    #Don't want to just keep restarting a bad server
                    #if server.restart_count < 10:
                    #But maybe we do
                    server.do_all()
                except KeyError:
                    print "Key Error on %s; Time: %s"%(server_data['ip_addr'],time.strftime("%a, %b %d, %Y %H:%M:%S"))

            self.file.seek(0)
            self.file.write('Generation %i, Running processes %i jobs %i %s \n'%(generation, num_running, self.interface.get_num_incompletes(), time.strftime('%c')))
            self.file.truncate()
            self.file.flush()

            time.sleep(20)
        finished_string = 'Finished running generation %i. time taken %i num incompletes %i. time %s \n'%(self.interface.get_max_hand_gen(), time.time() - t,
                                                                                                 self.interface.get_num_incompletes(),
                                                                                                time.strftime('%c'))
        print finished_string
        
        self.file.seek(0)
        self.file.write(finished_string)
        self.file.truncate()
        self.file.flush()
        
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
