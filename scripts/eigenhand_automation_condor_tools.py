import subprocess

def send_condor_jobs():
    args = ["ssh", "jweisz@rabat.clic.cs.columbia.edu", "condor_rm jweisz; sleep 20;cd ./condor_output; condor_submit ./submit.graspit_dummy"]
    p = subprocess.Popen(args)
    print "sent condor jobs"


def get_active_condor_jobs():
    args = ["ssh", "jweisz@rabat.clic.cs.columbia.edu", "condor_q | grep [RI] | wc -l"]
    return int(subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]) - 1

def get_server_idle_level(server_name):
    args = ["ssh", server_name, "mpstat 1 1| awk '{print $12}'"]    
    s=subprocess.Popen(args, stdout=subprocess.PIPE)
    for i in range(3):
        get_output(s)
    idle_level = float(get_output(s))
    return idle_level

def get_multiserver_condor_jobs():
    active_jobs = 0
    server_list = ["jweisz@noether.cs.columbia.edu", "jweisz@rabat.clic.cs.columbia.edu"]
    for server in server_list:
        args = ["ssh", server, "condor_q | grep [RI] | wc -l"]
        active_jobs += int(subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]) - 1
    return active_jobs

def send_multiserver_condor_jobs():
    server_list = ["jweisz@noether.cs.columbia.edu", "jweisz@rabat.clic.cs.columbia.edu"]
    for server in server_list:
        args = ["ssh", server, "condor_rm jweisz; sleep 20;cd ./condor_output; condor_submit ./submit.graspit_dummy"]
        subprocess.Popen(args)
    print "sent condor jobs"
    
