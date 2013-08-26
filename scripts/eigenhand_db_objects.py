"""
Objects that encapsulate first class entities that interact with the postgres database
"""
from numpy import *




class DBObject(object):
    """@brief Base class for building objects from entries in a table in a database.

    This is a base class that creates objects from an entry in the database of
    a table. Every column of the row becomes a data member instance of the object.
    """
    def __init__(self, **kwargs):
        """
        @brief Constructor that builds an object that contains every keyword
        argument as a member variable

        i.e. bar = DBObject(foo = 5)
             returns an object bar where bar.foo = 5.

        @param kwargs - keyword argument dictionary to be made in to member variables

        @returns an object with kwargs as its member variables. 
        """
        for key in kwargs.keys():
            self.__dict__[key] = kwargs[key]


    def from_row_list(self, row, table_columns):
        """
        @brief constructor like function that sets the keys in an object from
        a list, using a list of table_column names as an index. Ignores keys that have
        no corresponding entry in the table_columns.

        @param row - A list of values taken from a row in a database
        @param table_columns - The names of each column in the row
    
        """
        for key in self.__dict__.keys():
            try:
                self.__dict__[key] = row[table_columns.index(key)]
            except:
                pass


    def from_row_dict(self, row):
        """
        @brief constructor like function that sets the keys in an object from a row dictionary, using
        the same keys as the member variable names in the object. 

        """
        for key in row.keys():
            self.__dict__[key] = row[key]


class Hand(DBObject):
    """@brief Class that encapsulates the database representation of the hand.  It derives from
       DBObject.

    """
    
    def __init__(self, hand_id = [], hand_name = [],
                 generation = [0], finger_id_list = [],
                 palm_scale=[1,1,1], finger_base_positions = [], energy_list = [], parents = [], fingers = [] ):
        if energy_list == None:
            energy_list = []
        
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
    """
    @brief Class that encapsulates the database representation of the Tasks in the database. It
    derives from DBOject.
    """
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
    """@brief Exception thrown when an illegal finger is generated or seen
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class IllegalHandException(Exception):
    """@brief Exception thrown when an illegal hand is generated or seen.
    """
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
                 grasp_epsilon_quality = [], grasp_volume_quality = [], grasp_source_id = [], generation = -1):
        DBObject.__init__(self, grasp_id = grasp_id,
                          hand_id = hand_id,
                          scaled_model_id = scaled_model_id,
                          grasp_pregrasp_joints = grasp_pregrasp_joints,
                          grasp_grasp_joints = grasp_grasp_joints,
                          grasp_energy = grasp_energy,
                          grasp_epsilon_quality = grasp_epsilon_quality,
                          grasp_volume_quality = grasp_volume_quality,
                          grasp_source_id = grasp_source_id,
                          generation = generation)

        
    

def find_equivalent_dataobject(object_list, test_object, ignore_keys):
    """
    @brief Search a list of data objects for one which is equivalent in all of it's important
    propreties.

    @param object_list - The list of objects to search
    @param test_object - The object to match
    @param ignore_keys - The keys to ignore when looking for a match

    FIXME - This implementation is not that smart. A more pythonic version is probably possible. 

    @returns the matching object.       
    """
    def kill_entries_in_dict(d, keys):
        """
        @brief Remove certain keys from the dictionary

        @param d - The dictionary to remove from
        @param keys - They keys to remove. 
        """
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
    """
    @brief Find a finger that is the same in all aspects except the id.
    """
    return find_equivalent_dataobject(finger_list, f, ['finger_id'])


        
def find_equivalent_hand(hand_list,h):
    """
    @brief find a hand that is the same in all aspects except hand name,
    hand id, energy list, and generation
    """
    return find_equivalent_dataobject(hand_list, h, ['hand_id', 'energy_list','hand_name','generation','fingers'])



    
