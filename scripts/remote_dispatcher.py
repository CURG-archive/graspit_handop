import subprocess
import sh
import select

class RemoteServer(object):
    def __init__(self, server_name, interface):
        self.server_name = server_name
        self.kill_previous()
        self.filename = open("/dev/null","rw")
        self.subprocess = self.launch_job()
        self.interface = interface

    def launch_job(self):
        args = ["ssh", self.server_name, "python", "/home/jweisz/gm/graspit_dispatcher.py"]
        print "%s \n"%(self.server_name)
        return subprocess.Popen(args, stdin = subprocess.PIPE, stdout=self.filename, stderr=subprocess.STDOUT)

    def kill_previous(self):
        args = ["ssh", self.server_name, "killall", "python"]
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

    def run(self):
        running = 1
        while running:
            running = len([server for server in self.server_dict.values() if server.is_running()])
            
