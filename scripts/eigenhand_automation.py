import psycopg2
import psycopg2.extras
from numpy import *
import itertools
import random as rnd
import time
import copy as cp
from pylab import *
import subprocess
import socket
import select
import pdb
import sh

def get_num_unlaunched_jobs(interface):
    return len(interface.get_data_obj_by_index_list(Task, "task", "task_outcome_id", [1]))


def princomp(A,numpc=0):
     # computing eigenvalues and eigenvectors of covariance matrix
    M = (A-mean(A.T,axis=1)).T # subtract the mean (along columns)
    [latent,coeff] = linalg.eig(cov(M))
    p = size(coeff,axis=1)
    idx = argsort(latent) # sorting the eigenvalues
    idx = idx[::-1]       # in ascending order
    # sorting eigenvectors according to the sorted eigenvalues
    coeff = coeff[:,idx]
    latent = latent[idx] # sorting eigenvalues
    if numpc < p and numpc > 0:
         coeff = coeff[:,range(numpc)] # cutting some PCs
    score = dot(coeff.T,M) # projection of the data in the new space
    return coeff,score,latent




class DBObject(object):
    def __init__(self, **kwargs):
        for key in kwargs.keys():
            self.__dict__[key] = kwargs[key]

    def from_row_list(self, row, table_columns):
        for key in self.__dict__.keys():
            try:
                self.__dict__[key] = row[table_columns.index(key)]
            except:
                pass

    def from_row_dict(self, row):
        for key in row.keys():
            self.__dict__[key] = row[key]


class Hand(DBObject):
    def __init__(self, hand_id = [], hand_name = [],
                 generation = [0], finger_id_list = [],
                 palm_scale=[1,1,1], finger_base_positions = [], energy_list = [], parents = [], fingers = [] ):
        
        DBObject.__init__(self, hand_id = hand_id,
                          hand_name = hand_name,
                          palm_scale = palm_scale,
                          finger_id_list = finger_id_list,
                          finger_base_positions = finger_base_positions,
                          generation = generation,
                          energy_list = energy_list,
                          parents = parents,
                          fingers = fingers)
        



class Task(DBObject):
    def __init__(self, task_id=[], task_time = [], scaled_model_id=[], hand_id=[],
                 task_type_id=[], task_outcome_id=[], comment = [], parameters = []):
        DBObject.__init__(self, task_id = task_id,
                          task_time = task_time,
                          scaled_model_id = scaled_model_id,
                          hand_id = hand_id,
                          task_type_id = task_type_id,
                          task_outcome_id = task_outcome_id,
                          comment = comment,
                          parameters = parameters)
        
        
class IllegalFingerException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class IllegalHandException(Exception):
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

    
class Finger(DBObject):
    def __init__(self, finger_id = [], link_length_list = [], joint_range_list = [], joint_default_speed_list = []):
        DBObject.__init__(self,
                          finger_id = finger_id,
                          link_length_list = link_length_list,
                          joint_range_list = joint_range_list,
                          joint_default_speed_list = joint_default_speed_list)

        if (len(self.joint_range_list) != len(self.link_length_list)*2
            or len(self.link_length_list) != len(self.joint_default_speed_list)):
            raise IllegalFingerException("invalid finger parameters")
    
    

class Grasp(DBObject):
    def __init__(self, grasp_id = [], hand_id = [], scaled_model_id = [],
                 grasp_pregrasp_joints = [], grasp_grasp_joints = [], grasp_energy = [],
                 grasp_epsilon_quality = [], grasp_volume_quality = [], grasp_source_id = []):
        DBObject.__init__(self, grasp_id = grasp_id,
                          hand_id = hand_id,
                          scaled_model_id = scaled_model_id,
                          grasp_pregrasp_joints = grasp_pregrasp_joints,
                          grasp_grasp_joints = grasp_grasp_joints,
                          grasp_energy = grasp_energy,
                          grasp_epsilon_quality = grasp_epsilon_quality,
                          grasp_volume_quality = grasp_volume_quality,
                          grasp_source_id = grasp_source_id)

        
    


class EGHandDBaseInterface(object):
    def __init__(self):
        self.connection = psycopg2.connect("dbname='eigenhanddb' user='postgres' password='roboticslab' host='tonga.cs.columbia.edu'")
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
    def get_table_columns(self, table_name):
        self.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name ='%s'"%table_name);
        return [s[0] for s in self.cursor.fetchall()]
    
    def get_hand(self, hand_id):
        self.cursor.execute("SELECT * FROM hand WHERE hand_id =%i"%hand_id);
        h = Hand()
        h.from_row_dict(self.cursor.fetchone())
        return h

    def get_finger(self, finger_id):
        self.cursor.execute("SELECT * FROM finger WHERE finger_id =%i"%finger_id);
        f = Finger()
        f.from_row_dict(self.cursor.fetchone())
        return f

    def load_hand(self, hand_id):
        h = self.get_hand(hand_id)
        h.fingers = []
        for f_id in h.finger_id_list:
            h.fingers.append(self.get_finger(f_id))
        return h

    def get_grasps_for_hands(self, hand_id_list):
        grasp_list = []
        hand_id_list_str = 'array[' + ','.join([str(i) for i in hand_id_list]) + ']'
        if hand_id_list_str == []:
            return grasp_list
        try:
            self.cursor.execute("SELECT * from grasp where hand_id = ANY(%s)"%hand_id_list_str)
        except:
            print hand_id_list
            return grasp_list
        for r in range(self.cursor.rowcount):
            row = self.cursor.fetchone()
            g = Grasp()
            g.from_row_dict(row)
            grasp_list.append(g)
        return grasp_list
    
    def get_hand_ids_for_generation(self, generation, highest_only = False):
        if highest_only:
            self.cursor.execute("select hand_id from hand where generation[array_length(generation,1)]=%i"%(generation))
        else:
            self.cursor.execute("SELECT hand_id from hand where %i = ANY(generation)"%(generation))
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def load_grasps_for_generation(self, generation, highest_only = False):
        hand_ids = self.get_hand_ids_for_generation(generation, highest_only)
        return self.get_grasps_for_hands(hand_ids)

    def load_hands_for_generation(self, generation, highest_only = False):
        hand_ids = self.get_hand_ids_for_generation(generation, highest_only)
        return [self.load_hand(h) for h in hand_ids]
    
    

    def reset_database(self):
        self.cursor.execute("delete from task;")
        self.cursor.execute("delete from grasp;")
        self.cursor.execute("delete from hand where hand_id > 312;")
        self.connection.commit()

    @staticmethod
    def get_value_str(value):
        if (type(value) == type("")):   #If the data type is a string, put it in as a string
            return "'" + value + "'"        
        elif(hasattr(value, 'append')): #If the data type is iterable put it in as an array
            return "array%s"%str(value)
        else:
            return str(value)
            
    def get_insert_command(self, table_name, data_object, keys = [], return_key = [], exclude_keys = []):
        if not keys:
            keys = data_object.__dict__.keys()

        if return_key:
            keys.remove(return_key)
            
        for key in exclude_keys:
            keys.remove(key)

        keys_copy = list(keys)

        for key in keys_copy:
            if data_object.__dict__[key] == [] or data_object.__dict__[key] == None:
                keys.remove(key)
            
        key_list = ','.join(keys)
        
        command_str = "INSERT into " + table_name + " ("
        command_str += key_list
        command_str += ") VALUES ("

                        
            
        value_str_list = [self.get_value_str(data_object.__dict__[key]) for key in keys]

        value_str = ','.join(value_str_list)
        command_str += value_str + ")"
        if return_key:
            command_str += " RETURNING %s" %return_key
        
        return command_str
        
    def get_rows_by_index_list(self, table_name, index_name, index_list):
        command_str = "Select * from %s where %s = ANY(%s)"%(table_name, index_name, self.get_value_str(index_list))
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()

    def get_data_obj_by_index_list(self, object_class, table_name, index_name, index_list):
        rows = self.get_rows_by_index_list(table_name, index_name, index_list)
        columns = self.get_table_columns(table_name)
        object_list = list()
        for row in rows:
            obj = object_class()
            obj.from_row_list(row, columns)
            object_list.append(obj)
        return object_list
    
    def get_data_obj_from_table(self, object_class, table_name):
        command_str = "Select * from %s"%(table_name)
        self.cursor.execute(command_str)
        self.connection.commit()
        object_list = list()
        rows = self.cursor.fetchall()
        columns = self.get_table_columns(table_name)
        for row in rows:
            obj = object_class()
            obj.from_row_list(row, columns)
            object_list.append(obj)
        return object_list
    

    def add_finger_to_db(self, finger):                    
        command_str = self.get_insert_command(table_name = "finger", data_object = finger, keys = [], return_key ='finger_id')        
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]
    
    def add_hand_to_db(self, hand):
        command_str = self.get_insert_command(table_name = "hand", data_object = hand, keys = [], return_key ='hand_id', exclude_keys = ['fingers'])
        print command_str
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]

    def add_task_to_db(self, task):        
        command_str = self.get_insert_command(table_name = "task", data_object = task, return_key='task_id')
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]
    
    def update_hand_energy(self, hand):
        command_str = "update hand set energy_list=%s where hand_id=%s"%(self.get_value_str(hand.energy_list),
                                                                         self.get_value_str(hand.hand_id))
        self.cursor.execute(command_str)
        self.connection.commit()

    def update_hand_generation(self, hand):
        command_str = "update hand set generation=%s where hand_id=%s"%(self.get_value_str(hand.generation),
                                                                         self.get_value_str(hand.hand_id))
        self.cursor.execute(command_str)
        self.connection.commit()

    def get_best_hands(self, num_hands):
        command_str = "select distinct(hand_id) hand_id from (select * from hand order by unnest(energy_list) desc) alias limit %i;"%(num_hands)
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()

    def reset_incompletes(self):
        command_str = "update task set task_outcome_id = 1 where task_outcome_id = 2;"
        self.cursor.execute(command_str)
        self.connection.commit()

    def set_incompletes_as_error(self):
        command_str = "update task set task_outcome_id = 4 where (task_outcome_id = 2 or task_outcome_id = 1);"
        self.cursor.execute(command_str)
        self.connection.commit()

    def set_task_outcome_id(self, task_id, outcome_id):
        command_str = "update task set task_outcome_id = %i where task_id = %i"%(outcome_id, task_id)
        self.cursor.execute(command_str)
        self.connection.commit()

    
        

def find_equivalent_dataobject(object_list, test_object, ignore_keys):
    def kill_entries_in_dict(d, keys):
        for key in keys:
            d[key] = []
        return d                

    test_object_dict = kill_entries_in_dict(dict(test_object.__dict__), ignore_keys)

    for object_ in object_list:
        object_dict = kill_entries_in_dict(dict(object_.__dict__), ignore_keys)
        if object_dict == test_object_dict:
            return object_
    return []
    
    


def find_equivalent_finger(finger_list, f):
    return find_equivalent_dataobject(finger_list, f, ['finger_id'])


        
def find_equivalent_hand(hand_list,h):        
    return find_equivalent_dataobject(hand_list, h, ['hand_id', 'energy_list','hand_name','generation','fingers'])


def insert_unique_finger(interface, finger, finger_list):
    equivalent_finger = find_equivalent_finger(finger_list, finger)
    if(equivalent_finger):
        return equivalent_finger
    
    finger = cp.deepcopy(finger)
    finger.finger_id = interface.add_finger_to_db(finger)[0]
    return finger

def insert_unique_hand(interface, hand, hand_list, finger_list):
    hand.fingers = [insert_unique_finger(interface, finger, finger_list) for finger in hand.fingers]
    hand.finger_id_list = [finger.finger_id for finger in hand.fingers]
    equivalent_hand = find_equivalent_hand(hand_list, hand)    
    if equivalent_hand:
        hand.hand_id = equivalent_hand.hand_id
        interface.update_hand_generation(hand)
        return equivalent_hand
    hand.hand_id = interface.add_hand_to_db(hand)[0]
    return hand
    




def test_insert_hand(e):
    h = Hand(4,"EIGENHAND_test", 1, [1,1,1,1], [1,1,1],[0,90,180,270], [], [-1,-1])
    return e.add_hand_to_db(h)



def test_insert_task(e):
    t = Task(3,1000, 18000,1,3,1,"fakeworld.xml")
    return e.add_task_to_db(t)



def test_insert_finger(e):
    f = Finger(1,[1,1,1],[-180,180,-180,180,-180,180],[1,1,1])
    return e.add_finger_to_db(f)

    
world_list = ["fakeworld1.xml", "fakeworld2.xml"]


def get_output(subproc):
    t = ''
    while t == '':
        t = subproc.stdout.readline()
 
    return t


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

def kill_job_on_server(server_name, process_id):
    args = ["ssh", server_name, "pkill %i"%(process_id)]
    subprocess.Popen(args)
    print "killed job %i on %s"%(process_id, server_name)
    return

    
def get_grasps_by_hand(grasp_list):
    grasps_by_hand = dict()
    for g in grasp_list:
        try:
            grasps_by_hand[g.hand_id].append(g)
        except KeyError:
            grasps_by_hand[g.hand_id] = list([g])
    return grasps_by_hand

def get_grasps_by_scaled_model(grasp_list):
    grasps_by_scaled_model = dict()
    for g in grasp_list:
        try:
            grasps_by_scaled_model[g.scaled_model_id].append(g)
        except KeyError:
            grasps_by_scaled_model[g.scaled_model_id] = list([g])
    return grasps_by_scaled_model

def get_top_grasps_by_hand(grasp_list, number_grasps_per_object):
    top_grasp_dict = dict()
    def get_top_grasps_in_list(grasp_list, number):
        return sorted(grasp_list, key = lambda grasp:grasp.grasp_energy)[:number]
    grasps_by_hand = get_grasps_by_hand(grasp_list)
    for hand_id in grasps_by_hand:
        grasp_hand_list = grasps_by_hand[hand_id]
        grasps_by_scaled_model = get_grasps_by_scaled_model(grasp_hand_list)
        top_grasp_dict[hand_id] = []
        for scaled_model in grasps_by_scaled_model:
            top_grasp_dict[hand_id].extend(get_top_grasps_in_list(grasps_by_scaled_model[scaled_model],
                                                                  number_grasps_per_object))
    return top_grasp_dict


class GenerationManager (object):
    def __init__(self, interface, task_prototype_list, generation_number,
                 trial_len = 1000, trials_per_task=5, task_type_id = 4, eval_function=max):
        self.interface = interface
        self.task_prototype_list = task_prototype_list
        self.trial_len = trial_len
        self.task_type_id = task_type_id
        self.generation = generation_number
        self.eval_function = eval_function
        self.hand_id_list = []
        self.hands = []
        self.load_hands()
        self.trials_per_task = trials_per_task
        self.task_list = list()

    def load_hands(self):
        self.hands = self.interface.load_hands_for_generation(self.generation, True)    
        self.hand_id_list = [hand.hand_id for hand in self.hands]
        
    def insert_tasks(self):    
        for hand in self.hand_id_list:
            for p in self.task_prototype_list:
                t = Task(task_id = [], #set automatically
                         task_time = self.trial_len,
                         scaled_model_id = p.scaled_model_id,
                         hand_id = hand,
                         task_type_id = self.task_type_id,
                         task_outcome_id = 1,
                         comment = p.world,
                         parameters = [t*10**6 for t in p.wrench])
                for i in range(self.trials_per_task):
                    t.task_id = self.interface.add_task_to_db(t)
                    self.task_list.append(t)
        return

    def get_all_grasps(self):
        return self.interface.load_grasps_for_generation(self.generation, True)

    def get_sorted_grasps(self):
        return get_grasps_by_hand(self.interface.load_grasps_for_generation(self.generation, True))

    def get_all_top_sorted_grasps(self, number_grasps_per_object):

        return get_top_grasps_by_hand(self.interface.load_grasps_for_generation(self.generation, True),
                                      number_grasps_per_object)

    def finished(self):    
        self.task_list = self.interface.get_data_obj_by_index_list(Task, "task", "hand_id", self.hand_id_list)
        return not len([t for t in self.task_list if t.task_outcome_id  < 3])

    def start_generation(self):
        self.load_hands()
        self.insert_tasks()
#        send_condor_jobs()

    def next_generation(self):        
        self.generation += 1
        self.start_generation()


    
                      
def flatten(it):
        ret_list = []
        for i in it:
            ret_list.extend(i)
        return ret_list

def ATR_hand(grasp_list, hand):    
    """For each finger, get range of the joint
    """
    joint_extreme_list = flatten([f.joint_range_list for f in hand.fingers])
    
    joint_range_list = array([(joint_extreme_list[2*i + 1] - joint_extreme_list[2*i])/2 for i in range(len(joint_extreme_list)/2)])    
    
    joint_angle_mat = array([g.grasp_grasp_joints[1:] for g in grasp_list])*(180.0/pi)
    
    joint_mean = mean(joint_angle_mat,0)
    joint_stdev = std(joint_angle_mat,0)

    
    g_util = divide(joint_stdev,joint_range_list)

    #ways of chosing to expand or demote indices    
    reduction_threshold = .25
    expansion_threshold = .75
    
    #demotion_indices = [i for i in range(len(g_util)) if g_util[i] <= reduction_threshold
    demotion_indices = argsort(g_util)[:2]
    expansion_indices = argsort(g_util)[-2:]#[[i for i in range(len(g_util)) if g_util[i] > expansion_threshold]])[-4:]

    max_angle = 45    
    angle_step = 15

    new_joint_range_list = cp.deepcopy(joint_range_list)

    new_joint_range_list[demotion_indices] = [min(max_angle,floor(j/angle_step)*angle_step) for j in joint_range_list[demotion_indices]]
    
    new_joint_range_list[expansion_indices] = [min(max_angle, (floor(j/angle_step)+1) * angle_step) for j in joint_range_list[expansion_indices]]

    new_hand = cp.deepcopy(hand)

    j_offset = 0

    for f in new_hand.fingers:
        for j in range(len(f.link_length_list)):
            f.joint_range_list[2*j] = joint_mean[j + j_offset] - new_joint_range_list[j + j_offset]
            f.joint_range_list[2*j + 1] = joint_mean[j + j_offset] + new_joint_range_list[j + j_offset]
        j_offset += len(f.link_length_list)
    new_hand.parents = [hand.hand_id]
    new_hand.generation.append(hand.generation[-1] + 1)
    return new_hand


def ATR_generation(grasp_list, hand_list):
    grasp_dict = get_grasps_by_hand(grasp_list)
    new_hand_list = list()
    for hand in hand_list:
        try:
            new_hand_list.append(ATR_hand(grasp_dict[hand.hand_id], hand))
        except:
            print "error on hand %s"%(hand.hand_id)
    return new_hand_list

def vector_diff(d):
    return diff(array(d))

def GA_pair(h1, h2):

    parent_vector = [h1, h2]
    new_hand = Hand()

    #try to select a legal finger combination:
    parent_selector_vector = [0,0,1,1]
    child_angle_vector = []
    finger_selector_vector = []
    p1_finger_angle_vector = vector_diff(h1.finger_base_positions)
    p2_finger_angle_vector = vector_diff(h2.finger_base_positions)    
    finger_angle_vectors = [p1_finger_angle_vector, p2_finger_angle_vector]

    for i in range(10):
        finger_selector_vector = rnd.sample(parent_selector_vector,
                                                4)
        child_angle_vector = [0]
        for i in range(1,4):
            child_angle_vector.append(finger_angle_vectors[finger_selector_vector[i]][i-1] + child_angle_vector[-1])
        if child_angle_vector[-1] < 345:
            break

    if not child_angle_vector[-1] < 330:
        return []
    new_hand.finger_base_positions = child_angle_vector
    new_hand.finger_id_list = []   
    new_hand.fingers = []
    for i in range(4):
        new_hand.finger_id_list.append(parent_vector[finger_selector_vector[i]].finger_id_list[i])
        new_hand.fingers.append(parent_vector[finger_selector_vector[i]].fingers[i])
        
    palm_size_selector = rnd.randint(0,1)

    new_hand.palm_scale = parent_vector[palm_size_selector].palm_scale
    for finger in new_hand.fingers:
        finger.link_length_list[0] = new_hand.palm_scale[0]
        
    new_hand.generation = [max(h1.generation[-1], h2.generation[-1]) + 1]
    new_hand.parents = [h1.hand_id, h2.hand_id]
    new_hand.hand_name = "Eigenhand"
    return new_hand


def mutate_item(mean, std, increment, min_, max_):
        return max(min(round(rnd.gauss(mean,std)/increment)*increment, max_),min_)

def remove_link(finger, shrink_index):
    if shrink_index < len(finger.link_length_list): 
        return []
    del finger.link_length_list[shrink_index]
    del finger.joint_range_list[2*shrink_index: 2*shrink_index + 2]
    del finger.joint_default_speed_list.[shrink_index]        
    return finger


def remove_phalange(finger, link_num):
    new_finger = cp.deep_copy(finger)
    new_finger = remove_link(new_finger, link_num + 1)        
    new_finger = remove_link(new_finger, link_num)
    return new_finger


def split_phalange(finger, link_num):
    new_finger = cp.deep_copy(finger)

    #Insert a the new joint lengths
    new_finger.link_length_list.insert(link_num + 2, new_finger.link_length_list[link_num])
    new_finger.link_length_list.insert(link_num + 2, new_finger.link_length_list[link_num+1])

    #insert new joint ranges
    #These will be a copy of the old ranges
    joint_range_index = 2*link_num
    joint_range_to_copy = new_finger.joint_range_list[joint_range_index:joint_range_index + 4]
    #Do the insertion
    new_finger.joint_range_list[joint_range_index + 4:1] = joint_range_to_copy
    
    
    return new_finger

def GA_mutate(hand, rel_stdev):


    mutation_probability = .25

    finger_min_len = .25
    finger_max_len = 1
    finger_len_increment = .125
    finger_len_dev = rel_stdev*(finger_max_len - finger_min_len)
    
    palm_min_diameter = .75
    palm_max_diameter = 1.25
    palm_diameter_increment = .25
    palm_diameter_dev = rel_stdev * (palm_max_diameter - palm_min_diameter)


    finger_position_change_min = 30
    finger_position_change_max = 315
    finger_position_increment = 15
    finger_position_dev = 45 * rel_stdev

    new_hand = cp.deepcopy(hand)


    """mutate finger position around the base"""
    finger_position_mutation_probability = .25
        
    d = new_hand.finger_base_positions
    finger_position_diffs = vector_diff(d)

    """Finger positions are actually stored as their absolute position,
     but they are modified as their relative position.
    """

    for i in range(len(finger_position_diffs)):
        if rnd.random() < finger_position_mutation_probability:
            continue
        finger_position_diffs[i] = mutate_item(finger_position_diffs[i], finger_position_dev,
                                               finger_position_increment, finger_position_change_min, finger_position_change_max)
   
    new_positions =  cumsum(finger_position_diffs)
    new_hand.finger_base_positions[1:] = new_positions
    if new_hand.finger_base_positions[-1] > 340:
        return []
    
    if new_hand.finger_base_positions[1] < 20:
        return []

   

    """mutate finger length"""
    for i in range(len(hand.fingers)):
        new_hand.fingers[i] = cp.deepcopy(hand.fingers[i])        

    new_hand.finger_id_list = []
    for f in new_hand.fingers:
        for i in [3,5,7,9]: #for i in range(len(f.link_length_list)):
            if i > f.link_length_list:
                continue
            if rnd.random() < mutation_probability:
                f.link_length_list[i] = mutate_item(f.link_length_list[i], finger_len_dev,
                                                    finger_len_increment, finger_min_len, finger_max_len)
    
    
    
    """mutate palm"""
    palm_mutation_probability = .25
    palm_size_max = 1.25
    palm_size_min = .75
    palm_size_increment = .25
    palm_mutation_dev = (palm_size_max - palm_size_min) * rel_stdev
    palm_size = hand.palm_scale[0]
    
    if rnd.random() < palm_mutation_probability:
        palm_size = mutate_item(hand.palm_scale[0], palm_mutation_dev, palm_size_increment, palm_size_min, palm_size_max)

    new_hand.palm_scale = [palm_size, 1, palm_size]  
    for finger in new_hand.fingers:
        finger.link_length_list[0] = palm_size

    new_hand.generation = [hand.generation[-1] + 1]
    new_hand.parents = [hand.hand_id]
    return new_hand
            

def GA_generation(grasp_list, hand_list, eval_functor, rel_stdev):
    new_hand_list = list()
    
    grasp_dict = get_grasps_by_hand(grasp_list)
    hand_dict = dict()    

    for h in hand_list:
        hand_dict[h.hand_id] = h

    energy_list = list()

    for k in hand_dict:
        try:
            energy_list.append(eval_functor(grasp_dict[k],hand_dict[k]))
        except:
            print k
            energy_list.append(1e10)

    sorted_key_indices = [hand_dict.keys()[i] for i in argsort(energy_list)]
    elite_list_len = 4
    elite_hand_list = [hand_dict[k] for k in sorted_key_indices[:elite_list_len]]
    
    hand_pair_list = itertools.combinations(elite_hand_list, 2)
    
    for pair in hand_pair_list:
        new_hand = GA_pair(pair[0], pair[1])
        if new_hand:
            new_hand_list.append(new_hand)

    mutation_number = 6
    
    rand_ind_list = [rnd.randrange(0,elite_list_len) for i in range(mutation_number)]

    for ind in rand_ind_list:
        new_hand = []
        for i in range(10):
            new_hand = GA_mutate(elite_hand_list[ind], rel_stdev)
            if new_hand:
                break
        new_hand_list.append(new_hand)

    for hand in elite_hand_list:
        hand.generation.append(hand.generation[-1] + 1)
        new_hand_list.append(hand)
        
    return new_hand_list



def insert_new_finger(finger, finger_list, interface):
    if(not find_equivalent_finger(finger_list, finger)):
        return interface.add_finger_to_db(finger)
    return -1
        


def insert_new_hand(hand, hand_list, interface):
    if(not find_equivalent_hand(hand_list, hand)):
        return interface.add_hand_to_db(hand)
    return -1



def insert_entire_hand(hand, hand_list, finger_list, interface):
    for f in hand.fingers:
        f_ind = insert_new_finger(f, finger_list, interface)
        if f_ind > 0:
            f.finger_ind = f_ind
    hand.finger_id_list = [finger.finger_id for finger in hand.fingers]
    return insert_new_hand(hand, hand_list, interface)
        

def insert_hand_list(new_hand_list, interface):
    finger_list = interface.get_data_obj_from_table(Finger, 'finger')
    hand_list = interface.get_data_obj_from_table(Hand, 'hand')
    for hand in new_hand_list:
        new_hand_id = insert_entire_hand(hand, hand_list, finger_list, interface)
        if new_hand_id > 0:
            hand.hand_id = new_hand_id
    return new_hand_list


    


def evaluate_generation_energy(interface, eval_function, generation):    

    grasps = interface.load_grasps_for_generation(generation)
    grasps_by_hand = get_grasps_by_hand(grasps)
    
    grasp_group_energy = dict()

    for grasp_group in grasps_by_hand:
        grasp_group_energy[grasp_group[0].hand_id] = eval_function(grasp_group)
    
    return grasp_group_energy



def update_group_energies(interface, grasp_group_energy):
    for energy, hand_id in zip(grasp_group_energy.values(), grasp_group_energy.keys()):
        h = interface.get_hand(hand_id)
        h.energy_list.append(energy)
        interface.update_hand_energy(h)

    return


def test_insert_unique_hand(hand, interface):
    db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
    db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
    insert_unique_hand(interface, hand, db_hand_list, db_finger_list)


class TaskModel(object):
    def __init__(self, scaled_model_id=[], name=[], world=[], wrench = []):
        self.scaled_model_id = scaled_model_id
        self.name = name
        self.world = world
        self.wrench = wrench
        

model_dict = dict()
model_dict['hammer'] = TaskModel(18548,'harvard_hammer','worlds/HammerWorld.xml',[0,0,3.5,0,-4.55,0])
model_dict['drill'] = TaskModel(18547,'harvard_drill','worlds/DrillWorld2.xml',[0,0,24.52,.0,-2.25,0])
model_dict['doorknob'] = TaskModel(18546,'harvard_doorknob','worlds/DoorknobWorld.xml',[0,0,3.45,-.25,0,0])
model_dict['laptop'] = TaskModel(18545,'harvard_laptop','worlds/LaptopWorld.xml',[0,0,31.75,0,0,0])
model_dict['beerbottle'] = TaskModel(18544,'harvard_beerbottle','worlds/BeerbottleWorld.xml',[0,0,9.05,0,-0.45,0])
model_dict['sodabottle'] = TaskModel(18543,'harvard_sodabottle','worlds/TwoliterWorld.xml',[0,0,21.12,0,-1.57,0])
model_dict['wrench'] = TaskModel(18542,'harvard_wrench','worlds/WrenchWorld.xml',[0,3.25,0,-3.25,0])
model_dict['coffeemug'] = TaskModel(18541,'harvard_coffeemug','worlds/CoffeemugWorld.xml',[0,0,3.5,0,-4.55,0])
model_dict['bowl'] = TaskModel(18540,'harvard_bowl','worlds/BowlWorld.xml',[0,0,3.45,0,0,0])
model_dict['aerosol'] = TaskModel(18539,'harvard_aersol','worlds/AerosolcanWorld.xml',[0,0,3.55,0,0,0])


def top_mean_hand(grasp_list, hand, grasp_num=10):
    grasp_list.sort(key=lambda a:a.grasp_energy)
    return mean(array([g.grasp_energy for g in grasp_list[:grasp_num]]))


def calculate_ATE_scores(grasp_list, hand):
    def get_digit_coupling_complexity(finger_actuation_vector):
        return sum(abs(diff(finger_actuation_vector)))
    def get_grasp_joints(grasp_list):
        return array([g.grasp_grasp_joints for g in grasp_list])*(180.0/pi)

    def get_indices_for_finger(hand, finger_num):
        finger_start_ind = sum([len(finger.link_length_list) for finger in hand.fingers[:finger_num]])
        finger_end_ind = finger_start_ind + len(hand.fingers[finger_num].link_length_list)
        return finger_start_ind, finger_end_ind
        
    def get_finger_joints(hand, finger_num, grasp_joint_array):
        finger_start_ind, finger_end_ind = get_indices_for_finger(hand, finger_num)
        return grasp_joint_array[:,finger_start_ind:finger_end_ind]
    
    def get_truncated_eigenvectors(grasp_joint_array, capture_ratio):
        coeff,score,latent = princomp(grasp_joint_array)
        return coeff[:,nonzero(cumsum(latent/sum(latent)) >= capture_ratio)]

    def get_coupling(eigenvector, relevance_ratio):
        return(eigenvector > relevance_ratio)    
    
    
    def get_grasp_joint_array(grasp_list):
        joint_angle_mat = array([g.grasp_grasp_joints for g in grasp_list])*(180.0/pi)

    grasp_joints = get_grasp_joints(grasp_list)
    eigenvectors = get_truncated_eigenvectors(grasp_joints, .9)

    num_cols = eigenvectors.shape[2]
    num_fingers = len(hand.fingers)

    digit_coupling_complexity = zeros([num_cols, num_fingers])
    
    #iterate over columns
    for e_ind in range(num_cols):
        for f_ind in range(num_fingers):
            eigenvector = eigenvectors[:,0,e_ind]
            start_ind, end_ind = get_indices_for_finger(hand, f_ind)
            coupling = get_coupling(eigenvector[start_ind: end_ind], .2)
            digit_coupling_complexity[e_ind, f_ind] = get_digit_coupling_complexity(coupling)    

    actuator_complexity = zeros([1,num_fingers])
    for f_ind in range(num_fingers):
        for e_ind in range(num_cols):
            start_ind, end_ind = get_indices_for_finger(hand, f_ind)
            eigenvector = eigenvectors[start_ind:end_ind,0,e_ind]
            actuator_complexity[0,f_ind] += any(eigenvector > .2)

    #hand.energy_list = [digit_coupling_complexity, actuator_complexity]
    return digit_coupling_complexity, actuator_complexity

def ATE_hand(grasp_list, hand):
    alpha = .4
    beta = .6
    digit_coupling_complexity, actuator_complexity = calculate_ATE_scores(grasp_list, hand)
    return alpha*sum(sum(digit_coupling_complexity))*beta*sum(actuator_complexity)


def weighted_ATE_hand(grasp_list, hand):
    tmh = top_mean_hand(grasp_list, hand)
    if tmh < 0:
        tmh = -tmh
        #    else:
        #        print "hand %d mean energy > 0 "%(hand.hand_id)
        #        print tmh
        
    return tmh * ATE_hand(grasp_list, hand)


def get_all_scores(grasp_list, hand):
    tmh = top_mean_hand(grasp_list, hand)
    if tmh < 0:
        tmh = -tmh
        #    else:
        #        print "hand %d mean energy > 0 "%(hand.hand_id)
        #        print tmh
    digit_coupling_complexity, actuator_complexity = calculate_ATE_scores(grasp_list, hand)
    return tmh, digit_coupling_complexity, actuator_complexity

def calculate_digit_coupling_complexity(grasp_list, hand):
    return calculate_ATE_scores(grasp_list, hand)[0]
        
    
def run_tasks(gm, sleep_times, sleep_len):
    print "entering run tasks\n"
    for i in range(sleep_times):
        print "testing gm \n"
        if gm.finished():
            break
        print "finished gm \n"
        if not get_active_condor_jobs():
            print "resending condor jobs\n"
            gm.interface.reset_incompletes()
            send_condor_jobs()
            time.sleep(30)
        time.sleep(sleep_len)


def run_tasks2(gm):
    do_it(gm.interface)
    
        


def run_experiment(interface, generation, eval_functor):
    task_prototype_list = [model_dict[key] for key in model_dict]
    sleep_len = 10
    total_sleep_len = 10*600
    sleep_times = total_sleep_len / sleep_len
    gm = GenerationManager(interface,
                           task_prototype_list,
                           generation,
                           60,
                           5,
                           4,
                           eval_functor)
    gm.start_generation()
    num_ga_generations = 50
    
    for ga_gen_num in range(num_ga_generations):
        for atr_gen_num in range(5):
            # do atr five times                
            #run_tasks(gm, sleep_times, sleep_len)
            run_tasks2(gm)
            grasp_list = gm.get_all_grasps()
            new_hand_list = ATR_generation(grasp_list, gm.hands)
            for hand in new_hand_list:
                db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
                db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
                insert_unique_hand(interface, hand, db_hand_list, db_finger_list)
            gm.next_generation()
        #do ga
        #run_tasks(gm, sleep_times, sleep_len)
        run_tasks2(gm)
        grasp_list = gm.get_all_grasps()
        new_hand_list = GA_generation(grasp_list, gm.hands, eval_functor, .5-.4/num_ga_generations*ga_gen_num)
        for hand in new_hand_list:
            db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
            db_finger_list = interface.get_data_obj_from_table(Finger, "finger")            
            insert_unique_hand(interface, hand, db_hand_list, db_finger_list)
        gm.next_generation()
    
    run_tasks2(gm)




            
            
def test_ATE():
    interface = EGHandDBaseInterface()
    task_prototype_list = [model_dict['hammer']]
    gm = GenerationManager(interface,
                           task_prototype_list,
                           20,
                           15,
                           5,
                           4,
                           ATE_hand)
    gm.load_hands()
    grasp_dict = gm.get_all_top_sorted_grasps(10)
    e_list = dict()
    for key in grasp_dict:
        e_list[key] = [calculate_ATE_scores(grasp_dict[key], [h for h in gm.hands if h.hand_id == key][0])]
    return e_list


def test_mutate(hand_id):
    interface = EGHandDBaseInterface()
    hand = interface.load_hand(hand_id)
    
    hand2 = GA_mutate(hand, .5)
    
    return hand2

def generate_starting_set(starting_hand):
    current_hand = starting_hand
    hand_list = []
    for i in range(17):
        hand = []
        while not hand:
            hand = GA_mutate(current_hand,.5)
        current_hand = hand
        hand.generation = [0]
        hand_list.append(current_hand)
    return hand_list
        
def test_starting_set(hand_list):
    diffs = [vector_diff(hand.finger_base_positions) for hand in hand_list]
    return any([any(d < 30) for d in diffs])

def test_generate_starting_set(starting_hand):
    hand_list = generate_starting_set(starting_hand)
    return test_starting_set(hand_list)

def test_legal_mutate(hand_id, times  = 1000):
    nterface = EGHandDBaseInterface()
    hand = interface.load_hand(hand_id)
    hand_list = []
    for i in range(1000):
        hand2 = GA_mutate(hand, .5)
        if hand2:
            hand_list.append(hand2)
    print test_starting_set(hand_list)
    


        
def insert_unique_hand_list(hand_list, interface):
    for hand in hand_list:
        db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
        db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
        insert_unique_hand(interface, hand, db_hand_list, db_finger_list)


def test_load_hand(hand_num):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('loadEigenhand %i \n'%(hand_num))
    return

def test_scale_hand(chain_num, link_num, scale_vector):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('scaleRobotLink %i %i %i %i %i\n'%(chain_num, link_num, scale_vector[0], scale_vector[1], scale_vector[2]))
    return


def test_energy(energy_type = 0):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('getEnergy %i \n'%energy_type)




def test_next_atr(gm):
    gm.load_hands()
    gm.generation += 1
    grasp_list = gm.get_all_grasps()
    new_hand_list = ATR_generation(grasp_list, gm.hands)
    for hand in new_hand_list:
                db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
                db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
                insert_unique_hand(interface, hand, db_hand_list, db_finger_list)

server_dict = dict()
server_dict["128.59.15.74"] = []
server_dict["128.59.15.75"] = []
server_dict["128.59.15.71"] = []
server_dict["128.59.15.68"] = []
server_dict["128.59.15.73"] = []
server_dict["128.59.15.51"] = []
server_dict["128.59.15.69"] = []
server_dict["128.59.15.80"] = []
server_dict["128.59.15.57"] = []
server_dict["128.59.15.85"] = []
server_dict["128.59.15.55"] = []
server_dict["128.59.15.76"] = []
server_dict["128.59.15.50"] = []
server_dict["128.59.15.53"] = []
server_dict["128.59.15.77"] = []
server_dict["128.59.15.70"] = []
server_dict["128.59.15.79"] = []
server_dict["128.59.15.63"] = []
server_dict["128.59.15.48"] = []
server_dict["128.59.15.83"] = []
server_dict["128.59.15.56"] = []
server_dict["128.59.15.54"] = []
server_dict["128.59.15.58"] = []
server_dict["128.59.15.59"] = []
server_dict["128.59.15.49"] = []
server_dict["128.59.15.52"] = []
server_dict["128.59.15.84"] = []
server_dict["128.59.15.78"] = []
server_dict["128.59.15.72"] = []
server_dict["128.59.15.62"] = []

def test_servers():
    for server in server_dict:
        p = subprocess.Popen(['ssh',server,'touch me'])
        while p.returncode == None:
            p.poll()
        print "%s, %i"%(server, p.returncode)



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

simple_dict = dict()
simple_dict["rabat.clic.cs.columbia.edu"] = []

medium_dict = dict()           
medium_dict["128.59.15.78"] = []
medium_dict["128.59.15.72"] = []
medium_dict["128.59.15.62"] = []
                                  


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
            
            
            
            
def do_it(interface):
    t = time.time()
    r = 0
    job_num = get_num_unlaunched_jobs(interface)
    while job_num > 2:
        print r
        r += 1
        rd = RemoteDispatcher(server_dict, interface)
        rd.run()
        interface.reset_incompletes()
        job_num = get_num_unlaunched_jobs(interface)
    interface.set_incompletes_as_error()
    print "done.  Time %f \n"%(time.time() - t)
    
    

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

    

    
        
            
            
    

    


def test_job_dispatcher(interface):
    jd = JobDispatcher(simple_dict, interface)
    while(get_num_unlaunched_jobs(interface) > 0):
        jd.run_dispatcher()
        
        
