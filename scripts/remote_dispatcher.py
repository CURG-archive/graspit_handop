import subprocess
import select
import time
import pdb
import threading
import os
from ctypes import *

class RemoteServer(object):


    def __init__(self, server_name, interface):
        self.server_name = server_name
        self.interface = interface
        self.killed_forcibly = False
        self.dead_count = 0
        self.ssh_start_args = ["ssh", "-o", "ForwardX11=no", "-o","PasswordAuthentication=no", "-o","ConnectTimeout=30",server_name,"nohup"]
        self.ssh_end_args = [">>/home/jweisz/html/server_output/%s"%server_name, "2>&1", "</dev/null", "&"]

    def wrap_ssh_args(self,args):
        return self.ssh_start_args + args + self.ssh_end_args

    def launch_job(self):
        args = self.wrap_ssh_args(["/home/jweisz/gm/run_dispatcher.sh"])
        subprocess.Popen(args).wait()
        self.dead_count = 0

    def kill_client(self):
        args = self.wrap_ssh_args(["killall", "python", "graspit"])
        subprocess.Popen(args).wait()

    def do_all(self):        
        self.kill_client()
        self.launch_job()

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
        try:
            a = RemoteServer(server_name, self.interface)
            self.server_starting_dict[server_name] = a
            a.do_all()
            self.server_dict[server_name] = a
        except:
            print "Server %s failed to start"%(server_name)
        
    def kill_all_servers(self):
        for server in self.server_starting_dict.values():
            server.kill_client()

        self.file.close()

    def restart_dead_servers(self):
        nonrunning_server_data = self.interface.get_dead_servers(60*10)
        num_running = self.interface.get_num_running(60)
        for server_data in nonrunning_server_data:
            try:
                print "Restarting %s (%s); Time: %s"%(server_data['server_name'],server_data['ip_addr'],time.strftime("%a, %b %d, %Y %H:%M:%S"))
                server = self.server_dict[server_data['ip_addr']]
            except KeyError:
                print "Key Error on %s; Time: %s"%(server_data['ip_addr'],time.strftime("%a, %b %d, %Y %H:%M:%S"))

    def run(self, max_len = 9800):
        t = time.time()
        generation = self.interface.get_max_hand_gen()

        self.file.write('Started running generation %i at %s \n'%(generation,time.strftime('%c')))
        self.file.seek(0)
        self.file.flush()

        time.sleep(120)

        num_running = self.interface.get_num_running(60)
        while self.interface.get_num_incompletes() > 0 and time.time() - t < max_len and self.interface.get_num_running(60):

            self.file.seek(0)
            self.file.write('Generation %i, Running processes %i jobs %i %s \n'%(generation, num_running, self.interface.get_num_incompletes(), time.strftime('%c')))
            self.file.truncate()
            self.file.flush()

            time.sleep(20)
        finished_string = 'Finished running generation %i. time taken %i num incompletes %i. time %s \n'%(generation, time.time() - t, self.interface.get_num_incompletes(), time.strftime('%c'))
        print finished_string
        
        self.file.seek(0)
        self.file.write(finished_string)
        self.file.truncate()
        self.file.flush()

        #Just in case something failed out
        self.restart_dead_servers()
        
