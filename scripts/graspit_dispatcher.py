#! /usr/bin/env python
import subprocess
import socket
import time
from numpy import *
import select
import os
import random

class LocalDispatcher(object):
    def __init__(self):
        self.idle_percent = -1
        self.get_idle_percent()
        self.num_processors = self.get_num_processors()
        self.job_list = []
        self.min_server_idle_level = 20
        self.max_server_idle_level = 30
        self.server_name = socket.gethostname()
        self.kill_existing_graspit()
        
        
    def get_num_processors(self):
        args = ["cat /proc/cpuinfo | grep processor | wc -l"]
        s = subprocess.Popen(args, stdout=subprocess.PIPE, stdin = subprocess.PIPE, stderr=subprocess.STDOUT, shell = True)
        return int(s.stdout.readline())

    def get_idle_percent(self):
        args = ["mpstat 1 1 | awk '{print $12}'"]
        s = subprocess.Popen(args, stdout=subprocess.PIPE, stdin = subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        r = ''
        while 1:
            r = s.stdout.readline()
            try:
                self.idle_percent =  float(r)        
                return
            except:
                pass

        

    def get_num_to_launch(self):
        free_to_launch = int(floor((self.idle_percent - self.max_server_idle_level)/(100/self.num_processors)))
    	return min(free_to_launch, self.num_processors - len(self.job_list) - 2)


    def kill_existing_graspit(self):
        args = ["killall", "graspit"]
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stdin = subprocess.PIPE, stderr=subprocess.STDOUT)
        print "killall returned %s on %s\n"%(p.communicate()[0],self.server_name)
       
            
    def kill_last_job(self):
        if len(self.job_list) == 0:
            return False
        job_to_kill = self.job_list.pop()
        job_to_kill.kill()
        
        #job_to_kill.subprocess.communicate() #waits for job to finish
        print "%s busy. Killed task %i\n"%(self.server_name, job_to_kill.task_id)
        return True

    def kill_jobs_while_busy(self):
        self.get_idle_percent()
        while self.idle_percent < self.min_server_idle_level:
            cpu_per_job = 100/self.num_processors
            num_jobs_to_kill = int(floor((self.min_server_idle_level - self.idle_percent)/cpu_per_job)) + 1
            for i in range(num_jobs_to_kill):
                self.kill_last_job()
            self.get_idle_percent()

    def launch_job(self):
        self.job_list.append(LocalJob())
        #print self.job_list[-1].subprocess.stdout.readline()

    def launch_job_if_legal(self):
        if self.idle_percent > self.max_server_idle_level and len(self.job_list) < self.num_processors - 1:
            self.launch_job()
            print "%f on %s \n"%(self.idle_percent,self.server_name)
            return True
        return False

    def clear_inactive_jobs(self):
        job_list = [j for j in self.job_list if j.is_running()]
        dead_list = [j for j in self.job_list if not j.is_running()]
        for dead in dead_list:
            del dead
        
        try:
            if debug:
                for j in self.job_list:
                    if not j.is_running():
                        print "Clearing finished job %i task %i on server %s \n"%(j.subprocess.pid, j.task_id, self. server_name)
        except:
            pass
        self.job_list = job_list

    def launch_jobs_while_legal(self):
        self.get_idle_percent()
        for i in range(self.get_num_to_launch()):
            self.launch_job_if_legal()
        

    def get_task_ids(self):
        for j in self. job_list:
            j.get_task_id()

    def run_server(self):
        self.launch_jobs_while_legal()
        time.sleep(10)
        #self.get_task_ids()
        valid_jobs = [j for j in self.job_list if j.is_running()]
        if len(valid_jobs) == 0:
            print "no valid jobs on server %s\n"%(self.server_name)
            return False
        self.kill_jobs_while_busy()
        self.clear_inactive_jobs()
        return True

    def run_loop(self):
        while(self.run_server()):
            pass
        print "done\n"


class LocalJob(object):
    def __init__(self):
        self.status = []
        self.subprocess = []
        self.server_name = socket.gethostname()
        self.task_id = -1
        self.file = open("/dev/null","rw")
        self.start()

    def set_env(self):
        display_num = random.randint(0,3)
        os.putenv("MOSEKLM_LICENSE_FILE","/home/jweisz/gm/mosek_lib")
        os.putenv("LD_LIBRARY_PATH","/home/jweisz/gm/mosek_lib/")
        os.putenv("GRASPIT","/home/jweisz/gm/")
        os.putenv("GRASPIT_WAIT_DISPLAY_LEN","0")
        os.putenv("GRASPIT_QUIT_ON_TASK_COMPLETE","YES")
        server_name = "picard.cs.columbia.edu:%i.0"%(display_num)
        print server_name
        os.putenv("DISPLAY",server_name)
        os.putenv("CGDB_MODEL_ROOT","/home/jweisz/cgdb2")
        os.putenv("CGDB_MODEL_ROOT_FTP_URL","ftp://anonymous@tonga.cs.columbia.edu/")
        os.putenv("HAND_MODEL_ROOT_FTP_URL","ftp://anonymous@tonga.cs.columbia.edu/")
        os.putenv("GRASPIT_QUIT_ON_TASK_COMPLETE","YES")
        


    def start(self):
        self.set_env()
        args = "nice -n 50 /home/jweisz/gm/graspit test_planner_task PLAN_EGPLANNER_SIMAN use_console".split(" ")
        self.subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.file)

    def flush_std_out(self):
        if self.subprocess.returncode != None:
            return
        while(select.select([self.subprocess.stdout],[],[],0)[0]):
            if self.subprocess.stdout.readline()=='':
                break

    def is_running(self):
        #self.flush_std_out()
        self.subprocess.poll()
        if  self.subprocess.returncode != None:
            return False       
        return True

    def kill(self):
        if self.is_running():
            try:
                self.subprocess.kill()
                #l = self.subprocess.communicate()[0]
                while self.subprocess.poll() == None:
                    pass

                del self.subprocess
            except:
                pass
            
            if self.task_id > 0:
                self.warn_undone()

    def warn_undone(self):
        print ("task %i unfinished on %s\n")%(self.task_id, self.server_name)



    def reset_job(self, job_id):
        args = ["ssh", "tonga.cs.columbia.edu", "export PGPASSWORD=roboticslab; psql -c 'update task set task_outcome_id = 1, last_updater=%s where task_id = %i' -U postgres -d eigenhanddb -h tonga.cs.columbia.edu;"%(job_id, self.server_name)]
        s = subprocess.Popen(args,  stdout = subprocess.PIPE, stderr = subprocess.STDOUT, stdin = subprocess.PIPE)
        s.wait()

    def get_task_id(self):
        if self.task_id > 0:
            return True
        
        lines = []
        while(self.subprocess.poll() == None):
            line = self.subprocess.stdout.readline()
            lines.append(line)
            try:
                line_list = line.split(' ')
                t_index = line_list.index('Task_ID')
                self.task_id = int(line_list[t_index + 1])
                if self.task_id < 1:
                    
                    print lines
                    print "\n"
                    return False
                
                return True
            except:                
                pass
        try:
            if debug:
                print" printing output\n"
                print lines
        except:
            pass
        print "job %i failed to start when getting task id on server %s \n"%(self.subprocess.pid, self.server_name)
        self.kill()
        return False
            

if __name__ == "__main__":
    ld = LocalDispatcher()    
    ld.run_loop()
#    ld.kill_existing_graspit()


    

