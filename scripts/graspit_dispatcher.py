#! /usr/bin/env python
import os
import select
import random
import time
import datetime

import subprocess
import socket

from numpy import *

import psycopg2
import psycopg2.extras
import psutil

def make_path(path):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except:
            pass



class LocalDispatcher(object):
    def __init__(self):
        self.server_name = socket.gethostname()
        self.server_pid = os.getpid()
        self.ip_addr = socket.gethostbyname(self.server_name)

        self.kill_existing_graspit()

        self.min_server_idle_level = 10
        self.max_server_idle_level = 30
        self.idle_percent = self.get_idle_percent()
        self.num_processors = self.get_num_processors()

        self.job_list = []
        self.running_job_list = []
        self.suspended_job_list = []
        self.completed_job_list = []

        self.can_launch = True
        self.connection = psycopg2.connect("dbname='eigenhanddb' user='postgres' password='roboticslab' host='tonga.cs.columbia.edu'")
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            os.makedirs("/home/jweisz/html/graspit_handop/%s/%s_jobs"%(self.server_name,self.server_pid))
        except OSError:
            pass

        try:
            self.status_file = open('/home/jweisz/html/graspit_handop/%s/server_status'%(socket.gethostname()),'w')
        except:
            self.status_file = open('/dev/null','w')
            
    def get_num_processors(self):
        self.num_processors = psutil.NUM_CPUS
        return self.num_processors

    def get_idle_percent(self):
        self.idle_percent = 100.0 - psutil.cpu_percent()
        return self.idle_percent

    def get_num_to_launch(self):
        free_to_launch = int(floor((self.idle_percent - self.max_server_idle_level)/(100/self.num_processors)))
    	return min(free_to_launch, self.num_processors - len(self.job_list) - 3)


    def kill_existing_graspit(self):
        args = ["killall", "graspit"]
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stdin = subprocess.PIPE, stderr=subprocess.STDOUT)
        print "killall returned %s on %s\n"%(p.communicate()[0],self.server_name)

    def suspend_last_job(self):
        try:
            job_to_suspend = next(job for job in self.job_list if LocalJob.is_running(job))
            job_to_suspend.suspend()
        except StopIteration:
            return False 

        return True
    
    def kill_last_job(self):
        try:
            job_to_kill = next(job for job in self.job_list if LocalJob.is_running(job))
            job_to_kill.kill()
        except StopIteration:
            return False 
        
        #job_to_kill.subprocess.communicate() #waits for job to finish
        print "%s busy. Killed task %i\n"%(self.server_name, job_to_kill.task_id)
        return True

    def restore_job(self):
        try:
            job_to_restore = next(job for job in self.job_list[::-1] if LocalJob.is_suspended(job))
            job_to_restore.restore()
        except StopIteration:
            return False 

        return True
        

    def launch_job(self):
        job_lid = len(self.job_list) + 1
        #If newer jobs go near the front, we can suspend the newer ones easier
        self.job_list[:0] = [LocalJob(self,job_lid)]

    def launch_job_if_legal(self):
        num_alive = len([j for j in self.job_list if not j.is_done() or not j.is_dead()])
        if self.idle_percent > self.max_server_idle_level and num_alive< self.num_processors - 3:
            if not self.restore_job():
                #I don't love the happy go lucky happening here, fix in a bit
                self.launch_job()
            print "%f on %s \n"%(self.idle_percent,self.server_name)
            return True
        return False

    def launch_jobs_while_legal(self):
        if not self.can_launch:
            return
        self.get_idle_percent()
        for i in range(self.get_num_to_launch()):
            self.launch_job_if_legal()

    def suspend_jobs_while_busy(self):
        self.get_idle_percent()
        while self.idle_percent < self.min_server_idle_level:
            cpu_per_job = 100/self.num_processors
            num_jobs_to_suspend = int(floor((self.min_server_idle_level - self.idle_percent)/cpu_per_job)) + 1
            for i in range(num_jobs_to_suspend):
                self.suspend_last_job()
            time.sleep(10)
            self.get_idle_percent()

        
    def get_task_ids(self):
        for j in self.job_list:
            j.get_task_id()

    def run_server(self):
        self.update_jobs()
        #Clear out any problems
        self.suspend_jobs_while_busy()
        #Launch new jobs
        self.launch_jobs_while_legal()
        #Update the sql server
        self.update_status()
        return True


    def run_loop(self):
        while(self.run_server()):
            #Sleep, sweet dispatcher
            time.sleep(10)
	self.status_file.seek(0)
	self.status_file.write('Host: %s finished\n'%(socket.gethostname()))
	self.status_file.close()
        print "done\n"

    def update_jobs(self):
        for j in self.job_list:
            j.poll()

    def update_status(self):
        num_running = 0
        num_paused = 0
        num_killed = 0
        num_finished = 0
        for j in self.job_list
            num_running += j.is_running()
            num_paused += j.is_suspended()
            num_killed += j.is_dead()
            num_finished += j.is_done()

        self.get_idle_percent()

        self.cursor.execute("DELETE FROM servers WHERE server_name = %s AND server_pid = %s;",(self.server_name,self.server_pid))
        self.cursor.execute("INSERT INTO servers (server_name,server_pid,ip_addr,idle_percent,num_processors,running_jobs,paused_jobs,killed_jobs,finished_jobs) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);",(self.server_name,self.server_pid,self.ip_addr,self.idle_percent,self.num_processors,num_running,num_paused,num_killed,num_finished))
        self.connection.commit()
        self.output_status(num_running)

    def output_status(self, num_valid_jobs):
        status_string = "Host: %s  Idle level: %f Num running: %i Date: %s CanLaunch: %i\n"%(socket.gethostname(), self.idle_percent, num_valid_jobs, time.strftime('%c'), self.can_launch)
        print status_string
        self.status_file.seek(0)
        self.status_file.write(status_string)
        self.status_file.flush()

class LocalJob(object):
    def __init__(self, dispatcher, job_lid = -1):
        self.status = 1 #1 = running, 2 = suspended, 3 = killed, 4 = finished
        self.task_id = -1
        self.job_lid = job_lid #The id of the job on the local dispatcher
        self.exit_code = None

        self.subprocess = []
        self.dispatcher = dispatcher

        self.log_file = []
        if job_lid > 0:
            self.log_file = open('/home/jweisz/html/graspit_handop/%s/%s_jobs/%s'%(self.dispatcher.server_name,self.dispatcher.server_pid,self.job_lid), "a+")
        else:
            self.log_file = open("/dev/null","rw")

        self.start()

    def set_env(self):
        display_num = random.randint(1,4)
        os.putenv("MOSEKLM_LICENSE_FILE","/home/jweisz/gm/mosek_lib")
        os.putenv("LD_LIBRARY_PATH","/home/jweisz/gm/mosek_lib/")
        os.putenv("GRASPIT","/home/jweisz/gm/")
        os.putenv("GRASPIT_WAIT_DISPLAY_LEN","0")
        os.putenv("GRASPIT_QUIT_ON_TASK_COMPLETE","YES")
        server_name = "darcy.cs.columbia.edu:%i.0"%(display_num)
        print server_name
        os.putenv("DISPLAY",server_name)
        os.putenv("CGDB_MODEL_ROOT","/home/jweisz/cgdb2")
        os.putenv("CGDB_MODEL_ROOT_FTP_URL","ftp://anonymous@tonga.cs.columbia.edu/")
        os.putenv("HAND_MODEL_ROOT_FTP_URL","ftp://anonymous@tonga.cs.columbia.edu/")
        os.putenv("GRASPIT_QUIT_ON_TASK_COMPLETE","YES")
        
    def start(self):
        self.set_env()
        #        args = "nice -n 50 /home/jweisz/gm/graspit test_planner_task PLAN_EGPLANNER_SIMAN use_console".split(" ")
        args = "/home/jweisz/gm/graspit test_planner_task PLAN_EGPLANNER_SIMAN use_console".split(" ")
        self.log("Starting process from graspit_dispatcher")
        self.subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=self.log_file, stderr=self.log_file)

        self.dispatcher.cursor.execute("INSERT INTO jobs (server_name, job_lid, server_pid, last_updated) VALUES(%s,%s,%s,now())",[self.dispatcher.server_name,self.job_lid,self.dispatcher.server_pid])
        self.dispatcher.connection.commit()        

    def log(self,message):
        timestamp = datetime.datetime.now().isoformat()
        self.dispatcher.status_file.write("%s local job %s: %s\n"%(timestamp,self.job_lid,message))
        self.dispatcher.cursor.execute("INSERT INTO log(server_name, log_message) VALUES(%s,%s)",[self.dispatcher.server_name,'task %i: %s'%(self.job_lid,message)])
        self.dispatcher.connection.commit()        

    def poll(self):
        #There is never a reason to update a done job
        if(self.is_done()):
            return

        #Find out what it's been up to
        out, err = self.subprocess.communicate()
        if out is not None:
            self.log(out + " (graspit output)")
        if err is not None:
            self.log(err + " (graspit error)")

        #Find out if it's exited out
        self.subprocess.poll()
        if self.subprocess.returncode is not None:
            self.status = 4
            self.exit_code = self.subprocess.returncode

            self.dispatcher.can_launch = (self.exit_code != 5) #I/O IS IMPORTANT

            self.log("Process finished with return code %i"%self.exit_code)
            self.dispatcher.cursor.execute("UPDATE jobs SET exit_code = %s, end_time = now(),last_updated = now() WHERE server_name = %s AND job_lid = %s AND server_pid = %s;",[self.exit_code,self.dispatcher.server_name,self.job_lid,self.dispatcher.server_pid])
            self.dispatcher.connection.commit()        
        else:
            self.dispatcher.cursor.execute("UPDATE jobs SET last_updated = now() WHERE server_name = %s AND job_lid = %s AND server_pid = %s;",[self.dispatcher.server_name,self.job_lid,self.dispatcher.server_pid])
            self.dispatcher.connection.commit()        

    def is_running(self):
        return self.status == 1

    def is_suspended(self):
        return self.status == 2

    def is_dead(self):
        return self.status == 3

    def is_done(self):
        return self.status == 4

    def suspend(self):
        try:
            self.subprocess.send_signal(23)
            self.log("Suspending process from graspit_dispatcher")
            self.status = 2
        except:
            pass

    def restore(self):
	try:
	    self.subprocess.send_signal(19)
	    self.log("Restoring from graspit_dispatcher")
	except:
	    pass

    def kill(self):
        try:
            self.log("Killing process from graspit_dispatcher")
            self.subprocess.kill()
            while self.subprocess.poll() == None:
                pass

            del self.subprocess
        except:
            pass
            
        if self.task_id > 0:
            self.warn_undone()

    def warn_undone(self):
        self.log("Ended unfinished on %s\n"%(self.server_name))

    '''So...this isn't ever called. Huh.'''
    def reset_job(self, job_id):
        self.dispatcher.cursor.execute("UPDATE task SET task_outcome_id = 1, last_updater=%s WHERE task_id = %s",[job_id,self.server_name]);
        self.dispatcher.connection.commit()        

    '''This maybe doesn't make a large amount of sense. Look into later'''
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
        print "job %d failed to start when getting task id on server %s \n"%(self.subprocess.pid, self.server_name)
        self.kill()
        return False
            

if __name__ == "__main__":
    ld = LocalDispatcher()    
    ld.run_loop()
#    ld.kill_existing_graspit()


    

