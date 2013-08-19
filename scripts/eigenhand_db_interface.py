import psycopg2
import psycopg2.extras
import eigenhand_db_objects
import socket

#The task table outcome codes.
TASK_READY = 1
TASK_RUNNING = 2
TASK_SUCCEEDED = 3
TASK_ERROR = 4

class EGHandDBaseInterface(object):
    """@brief Class that allows high level control over the database for the eigenhand project.
    """

    def __init__(self):
        """@brief Connect to the postgres database.
        """
        self.connection = psycopg2.connect("dbname='eigenhanddb' user='postgres' password='roboticslab' host='tonga.cs.columbia.edu'")
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)


    def get_table_columns(self, table_name):
        """@brief Get an ordered list of the names of the columns of a table

        @param table_name - the name of the table to get the columns of.

        @returns a list of column names, in order of appearance in the table.
        """
        self.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name ='%s'"%table_name);
        return [s[0] for s in self.cursor.fetchall()]



    def get_hand(self, hand_id):
        """
        @brief Get a particular hand from the database by hand_id. Does not populate the finger
        descriptions, only gets the finger_ids associated with the hand.

        @param hand_id - The hand serial number to get

        @returns a Hand object populated from the database.
        """
        self.cursor.execute("SELECT * FROM hand WHERE hand_id =%i"%hand_id);
        h = eigenhand_db_objects.Hand()
        h.from_row_dict(self.cursor.fetchone())
        return h

    def get_finger(self, finger_id):
        """
        @brief Get a particular finger from the database by finger_id.

        @param hand_id - The hand serial number to get

        @returns a Hand object populated from the database.
        """
        self.cursor.execute("SELECT * FROM finger WHERE finger_id =%i"%finger_id);
        f = eigenhand_db_objects.Finger()
        f.from_row_dict(self.cursor.fetchone())
        return f



    def load_hand(self, hand_id):
        """
        @brief Get a hand with it's fingers loaded.

        @param hand_id - The hand serial number to load

        @returns a Hand object with a fingers member that is a list of Fingers
        corresponding to the finger_ids of the hand.
        """
        h = self.get_hand(hand_id)
        h.fingers = []
        for f_id in h.finger_id_list:
            h.fingers.append(self.get_finger(f_id))
        return h



    def get_grasps_for_hands(self, hand_id_list):
        """
        @brief Get all grasps from the database for a list of hand_ids.

        @param hand_id_list - a list of hand serial numbers

        @returns A list of all grasps for the hands in hand_id_list.
        """
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
            g = eigenhand_db_objects.Grasp()
            g.from_row_dict(row)
            grasp_list.append(g)
        return grasp_list



    def get_hand_ids_for_generation(self, generation, highest_only = False):
        """
        @brief get all hands that were present for a given generation.

        @param generation - The number of the generation to get.
        @param highest_only - Whether to get hands that were made only specifically for this generation.

        The hand's generation does not necessarily represent only the one in which it is made.
        A hand may be annotated with it's parent's generation also, if it is made by ATR or if it is carried forward from
        the previous iteration because it is more successful.

        """

        if highest_only:
            self.cursor.execute("select hand_id from hand where generation[array_length(generation,1)]=%i"%(generation))
        else:
            self.cursor.execute("SELECT hand_id from hand where %i = ANY(generation)"%(generation))
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]



    def load_grasps_for_generation(self, generation, highest_only = False):
        """
        @brief Get all grasps produced in this generation, for all hands in this generation.

        @param generation - The number of the generation to get.
        @param highest_only - Whether to load the hand if the generation for the hand is only the highest one that
        that hand is present in.

        @returns a list of all grasps planned in this generation.
        """
        hand_ids = self.get_hand_ids_for_generation(generation, highest_only)
        return self.get_grasps_for_hands(hand_ids)

    def load_hands_for_generation(self, generation, highest_only = False):
        """
        @brief Load all hands for this generation. Gets the hand data with the fingers loaded.

        @param generation - The number of the generation to get.
        @param highest_only - Whether to load the hand if the generation requested is the
                              highest one the hand is present in.

        @returns A list of loaded hands.
        """
        hand_ids = self.get_hand_ids_for_generation(generation, highest_only)
        return [self.load_hand(h) for h in hand_ids]



    def reset_database(self):
        """
        @brief Reset the database to it's starting condition. Deletes all tasks, grasps, and derived hands.

        Assumes that the starting set of hands is all hands with an id below 313.
        """
        self.cursor.execute("delete from task;")
        self.connection.commit()
        self.cursor.execute("delete from grasp;")
        self.connection.commit()
        self.cursor.execute("delete from hand;")
        self.connection.commit()
        self.cursor.execute("delete from finger;")
        self.connection.commit()


    def insert_gen_0(self):
        """
        @brief Insert the prestored hands and fingers from generation 0 in to the database
        """
        self.cursor.execute("insert into finger select * from finger_gen_0;")
        self.cursor.execute("insert into hand select * from hand_gen_0;")
        self.cursor.execute("select setval('finger_finger_id_seq',(select max(finger_id) from finger))")
        self.cursor.execute("select setval('hand_hand_id_seq',(select max(hand_id) from hand))")

        self.connection.commit()

    def prepare_gen_0(self):
        self.reset_database()
        self.insert_gen_0()

    def incremental_backup(self, base_filename = '/tmp/test', tables = ['finger','hand','grasp']):
        """
        @param filename - The filename to store to.
        @param tables - The name of the tables to backup

        """
        filenames = []
        d = dict()
        for table in tables:
            filename = base_filename + '_' + table
            d[table] = filename
            self.cursor.execute("COPY %s TO '%s'"%(table, filename))
            self.connection.commit()

        return d

    def incremental_restore(self, filename_dict):
        """
        @param filename_dict - Load data from filenames.
        """
        for table, filename in filename_dict.iteritems():
            self.cursor.execute("COPY %s FROM '%s'"%(table, filename))
            self.connection.commit()
        return

    @staticmethod
    def get_value_str(value):
        """
        @brief Helper function to turn a value in to a string that can be inserted in to the database

        @param value - The value to convert

        @returns a string that is appropriate to insert the given datatype.

        """
        if (type(value) == type("")):   #If the data type is a string, put it in as a string
            return "'" + value + "'"
        elif(hasattr(value, 'append')): #If the data type is iterable put it in as an array
            return "array%s"%str(value)
        else:
            return str(value)



    def get_insert_command(self, table_name, data_object, keys = [], return_key = [], exclude_keys = []):
        """
        @brief A helper function to insert a data object of the type from a derived class from DBObjects

        @param table_name - The name of the table to insert in to

        @param data_object - The object to insert

        @param keys - The keys to insert. Default value implies all data object keys should be inserted

        @param return_key - A key not to insert, but one that will instead be set as part of inserting the object
                            by the database itself, which will then be returned. Sequences such as the serial id of
                            an object is appropriate for this. This is generally used to return the id of a newly
                            inserted object.

        @param exclude_keys - A list of keys no to insert.
        """

        #If no keys have been set, use them all by default.
        if not keys:
            keys = data_object.__dict__.keys()

        #Now remove the key we expect to be set by the database when we insert this object
        if return_key:
            keys.remove(return_key)

        #Remove any additional keys we want to ignore.
        for key in exclude_keys:
            keys.remove(key)

        #Remove any keys that have invalid inputs. Any values unset will end up as empty anyway.
        keys_copy = list(keys)

        for key in keys_copy:
            if data_object.__dict__[key] == [] or data_object.__dict__[key] == None:
                keys.remove(key)

        #Now create the command.
        key_list_str = ','.join(keys)

        command_str = "INSERT into " + table_name + " ("
        command_str += key_list_str
        command_str += ") VALUES ("

        #Create the value list to be inserted, converted into strings
        #representing the appropriate datatypes
        value_str_list = [self.get_value_str(data_object.__dict__[key]) for key in keys]

        #Convert it to a string.
        value_str = ','.join(value_str_list)
        command_str += value_str + ")"

        #Add the request to return the return key
        if return_key:
            command_str += " RETURNING %s" %return_key

        return command_str



    def get_rows_by_index_list(self, table_name, index_name, index_list):
        """
        @brief Get all rows from a table that match any of the indices in a list.

        @param table_name - The name of the table to retrieve from.

        @param index_name - The name of the column from which to index

        @param index_list - The list of indices to retrieve

        @returns a list of lists of values for each row.
        """
        command_str = "Select * from %s where %s = ANY(%s)"%(table_name, index_name, self.get_value_str(index_list))
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()



    def get_data_obj_by_index_list(self, object_class, table_name, index_name, index_list):
        """
        @brief Get a set of objects from the database by a list of indices.

        @param object_class - The class of object to retrieve
        @param table_name - The name of the table to retrieve from.
        @param index_name - The name of the column from which to index
        @param index_list - The list of indices to retrieve.

        @returns a list of objects made from each row
        """
        rows = self.get_rows_by_index_list(table_name, index_name, index_list)
        columns = self.get_table_columns(table_name)
        object_list = list()
        for row in rows:
            obj = object_class()
            obj.from_row_list(row, columns)
            object_list.append(obj)
        return object_list

    def get_data_obj_from_table(self, object_class, table_name):
        """
        @brief Get a set of all objects from the table.

        @param object_class - The class of object to retrieve
        @param table_name - The name of the table to retrieve from

        @returns a list of objects of all rows from the table
        """
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
        """
        @brief Add a finger to the database, retrieves the index of the inserted object

        @param finger - The Finger object to insert.

        @returns the index of the inserted object.
        """
        command_str = self.get_insert_command(table_name = "finger", data_object = finger, keys = [], return_key ='finger_id')
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]

    def add_hand_to_db(self, hand):
        """
        @brief Add a Hand to the database, retrieves the index of the inserted object

        @param hand - The Hand object to insert.

        @returns the index of the inserted object.
        """
        command_str = self.get_insert_command(table_name = "hand", data_object = hand, keys = [], return_key ='hand_id', exclude_keys = ['fingers'])
        print command_str
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]

    def add_task_to_db(self, task):
        """
        @brief Add a Task to the database, retrieves the index of the inserted object

        @param task - The Task object to insert.

        @returns the index of the inserted object.
        """
        command_str = self.get_insert_command(table_name = "task", data_object = task, return_key='task_id')
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()[0]

    def update_hand_energy(self, hand):
        """
        @brief Store the energy from the Hand to the table, assuming the hand exists in the table.

        @param hand - The Hand's energy to store.
        """
        command_str = "update hand set energy_list=%s where hand_id=%s"%(self.get_value_str(hand.energy_list),
                                                                         self.get_value_str(hand.hand_id))
        self.cursor.execute(command_str)
        self.connection.commit()

    def update_hand_generation(self, hand):
        """
        @brief Store the generation of the Hand to the table, assuming the hand exists in the table.

        @param hand - The Hand which to update the generation of to store.

        """
        command_str = "update hand set generation=%s where hand_id=%s"%(self.get_value_str(hand.generation),
                                                                         self.get_value_str(hand.hand_id))
        self.cursor.execute(command_str)
        self.connection.commit()

    def get_best_hands(self, num_hands):
        """
        @brief Get the hand with the best energy

        @param num_hands - The number of hands to retrieve

        @returns A list of hand_ids that are the best.
        """
        command_str = "select distinct(hand_id) hand_id from (select * from hand order by unnest(energy_list) desc) alias limit %i;"%(num_hands)
        self.cursor.execute(command_str)
        self.connection.commit()
        return self.cursor.fetchall()

    def reset_incompletes(self):
        """
        @brief Sets all tasks that are still running back to the ready to run state.
        """
        command_str = "update task set task_outcome_id = 1, last_updater='%s' where task_outcome_id = 2;"%(socket.gethostname())
        self.cursor.execute(command_str)
        self.connection.commit()

    def set_incompletes_as_error(self):
        """
        @brief Sets all tasks that are still running to the error state.
        """
        command_str = "update task set task_outcome_id = 4, last_updater='%s' where (task_outcome_id = 2 or task_outcome_id = 1);"%(socket.gethostname())
        self.cursor.execute(command_str)
        self.connection.commit()

    def set_task_outcome_id(self, task_id, outcome_id):
        """
        @brief
        @param task_id - The task to update
        @param outcome_id - The outcome which to set it to.
        """
        command_str = "update task set task_outcome_id = %i, last_updater='%s' where task_id = %i"%(outcome_id, socket.gethostname(), task_id)
        self.cursor.execute(command_str)
        self.connection.commit()

