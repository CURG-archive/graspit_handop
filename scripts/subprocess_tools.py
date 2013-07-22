import subprocess

def get_output(subproc):
    """
    @brief read the output of the subprocess. Waits for the subprocess to actually output.

    @returns a string that is the output.    
    """
    t = ''
    while t == '':
        t = subproc.stdout.readline()
 
    return t




def kill_job_on_server(server_name, process_id):
    """
    @brief Kills a job by process id on a foreign server

    @param server_name - The url on which to kill the job

    @param process_id - The id of the process which to kill.

    """
    
    args = ["ssh", server_name, "pkill %i"%(process_id)]
    subprocess.Popen(args)
    print "killed job %i on %s"%(process_id, server_name)
    return


def test_servers():
    for server in server_dict:
        p = subprocess.Popen(['ssh',server,'touch me'])
        while p.returncode == None:
            p.poll()
        print "%s, %i"%(server, p.returncode)

