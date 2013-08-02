"""
@brief To upload the current version of the server side software, including the graspit binary,
the graspit_dispatcher and the graspit monitor, run python ./update_server_files.py from the command line on tonga.

Before uploading, run mk_linux_mosek, and then ./static_mosek_link_cmd on tonga.
"""
import subprocess

target_name = "jweisz@clic-lab.cs.columbia.edu:~/gm/"

file_names = ["graspit_dispatcher.py", "graspit_dispatch_monitor.py","../bin/graspit"]

def upload_file(file_name):
    args = ["scp", file_name, target_name]    
    s = subprocess.Popen(args)
    return s.poll()


if __name__ == "__main__":
    for fn in file_names:
        upload_file(fn)
