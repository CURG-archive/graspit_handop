import subprocess

class Server(object):
    def __init__(self, server_name, interface):
        self.query_state_subprocess = []
        self.idle_percent = -1
        self.job_list = []
        self.server_name = server_name
        self.max_server_idle_level = 30
        self.num_processors = self.get_num_processors()
        self.interface = interface
        
        
    def launch_idle_query(self):
        args = ["ssh", self.server_name, "mpstat 1 1| awk '{print $12}'"]
        self.query_state_subprocess = subprocess.Popen(args, stdout=subprocess.PIPE)

    def get_num_processors(self):
        args = ["ssh" , self.server_name, "cat /proc/cpuinfo | grep processor | wc -l"]
        s = subprocess.Popen(args, stdout=subprocess.PIPE)
        i = get_output(s)
        return int(i)

    def finish_idle_query(self):
        self.idle_percent = float(self.query_state_subprocess.communicate()[0].split('\n')[3])

    def clear_inactive_jobs(self):
        job_list = [j for j in self.job_list if j.job_is_active()]
        try:
            if debug:
                for j in self.job_list:
                    if not j.job_is_active():
                        print "Clearing finished job %i task %i on server %s"%(j.subprocess.pid, j.task_id, self. server_name)
        except:
            pass
        self.job_list = job_list

    def update_idle(self):
        self.launch_idle_query()
        self.finish_idle_query()


    def kill_last_job(self):
        if len(self.job_list) == 0:
            return False
        job_to_kill = self.job_list.pop()
        job_to_kill.kill()
        job_to_kill.subprocess.communicate() #waits for job to finish
        print "%s busy. Killed Job %i task %i\n"%(self.server_name, job_to_kill.subprocess.pid, job_to_kill.task_id)
        return True

    def kill_jobs_while_busy(self):
        self.update_idle()
        while self.idle_percent < self.min_server_idle_level:
            cpu_per_job = 10/self.num_processors
            num_jobs_to_kill = int(floor((self.min_server_idle_level - self.idle_percent)/cpu_per_job)) + 1
            for i in range(num_jobs_to_kill):
                self.kill_last_job()
            self.update_idle()

    def launch_job(self):
        self.job_list.append(Job(self.server_name, self.interface))

    def launch_job_if_legal(self):
        if self.idle_percent > self.max_server_idle_level:
            self.launch_job()
            return True
        return False

    def get_last_job_task_id(self):
        if self.job_list and self.job_list[-1].task_id == -1:
            return self.job_list[-1].get_task_id()
        return False




class JobDispatcher(object):
    def __init__(self, server_name_dict, interface):
        self.server_dict = dict()
        for server_name in server_name_dict:
            try:
                a = sh.ping(server_name,w=1)
            except:
                print "Couldn't ping %s"%(server_name)
                continue
            if a.exit_code:
                print "Couldn't ping %s"%(server_name)
                continue
            print "pinged %s"%(server_name)
            self.server_dict[server_name] = Server(server_name, interface)
        self.interface = interface


    def kill_job_on_busy_servers(self):
        for server in self.server_dict.values():
            server.kill_jobs_while_busy()
        

    def clear_inactive_jobs(self):
        for server in self.server_dict.values():
            server.clear_inactive_jobs()
        
    def run_dispatcher(self):
        while get_num_unlaunched_jobs(self.interface) and self.round_robin_launch():
            pass

        self.clear_inactive_jobs()

        self.kill_job_on_busy_servers()
        
                
    def round_robin_launch(self):
        legal_server_list = []
        for server in self.server_dict.values():
            #launch idle update
            server.launch_idle_query()
        for server in self.server_dict.values():
            server.finish_idle_query()
        for server in self.server_dict.values():
            if server.launch_job_if_legal():
                legal_server_list.append(server)
        for server in legal_server_list:
            server.get_last_job_task_id()
            
        return bool(len(legal_server_list))


simple_dict = dict()
simple_dict["rabat.clic.cs.columbia.edu"] = []
    
def test_job_dispatcher(interface):
    jd = JobDispatcher(simple_dict, interface)
    while(get_num_unlaunched_jobs(interface) > 0):
        jd.run_dispatcher()


JOB_DONE_STATUS = 3

class Job(object):
    def __init__(self, server_name, interface):
        self.status = []
        self.subprocess = []
        self.task_id = -1
        self.server_name = server_name        
        self.interface = interface
        self.start()

    def start(self):
        args = ["ssh", self.server_name, "cd gm; ./launch_nice"]
        self.subprocess = subprocess.Popen(args, stdin = subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def flush_std_out(self):
        while(select.select([self.subprocess.stdout],[],[],0)[0]):
            if self.subprocess.stdout.readline()=='':
                break

       
    
    def is_running(self):
        self.flush_std_out()     
        if self.subprocess.poll() != None:
            return False       
        return True

    def kill(self):
        if self.is_running():
            self.subprocess.kill()
            if self.task_id > 0:
                self.mark_undone()
    
    def mark_undone(self):
        self.interface.set_task_outcome_id(self.task_id, 1)

    def get_db_status(self):
        task = self.interface.get_data_obj_by_index_list(Task, "task", "task_id", [self.task_id])[0]
        return task.task_outcome_id

    def check_job_done(self):
        if self.task_id == -1:
            print "checked task without valid task id"
            return False
        
        if self.get_db_status() == JOB_DONE_STATUS:
            if self.is_running():
                self.subprocess.kill()
                print "Had to manually kill job %i on %s doing task %i even though it finished running\n"%(self.subprocess.pid, self.server_name, self.task_id)
            return True
        return False

    def job_is_active(self):
        if not self.check_job_done():
            if not self.is_running():
                print "job %i task %i on server %s died without finishing"%(self.subprocess.pid, self.task_id, self.server_name)
                self.mark_undone()
                return False
            return True
        return False
            
    def get_task_id(self):
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
        print "job %i on server %s failed to start when getting task id"%(self.subprocess.pid, self.server_name)
        print self.subprocess.communicate()[0]
        return False

