import eigenhand_db_objects

class GenerationManager (object):
    """
    @brief Manage all of the book keeping to run a generation's tasks. This means
    inserting all of the tasks to run the planners, retrieving all of the grasps
    afterwards, and loading all of the hands for the generation.
    """
    def __init__(self, interface, task_model_list, generation_number,
                 trial_len = 1000, trials_per_task=5, task_type_id = 4, eval_function=max):
        """
        @param interface - The interface to the database
        @param task_model_list - A list of dictionaries describing the model and associated
                                 worlds world to use to make the list of Tasks to insert in to the database
        @param trial_len - The length of trials to run
        @param trials_per_task - The number of planners to run per task.
        @param task_type_id - The identifier for the type of task to run
        @param eval_function - The function to use to assess what the top grasps are.
        """
        self.interface = interface
        self.task_model_list = task_model_list
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
        """
        @brief Load the hands for the current generation in to the member variable of this
        object.
        """
        self.hands = self.interface.load_hands_for_generation(self.generation, True)    
        self.hand_id_list = [hand.hand_id for hand in self.hands]
        
    def insert_tasks(self):
        """
        @brief Insert all of the tasks necessary to run this generation.        
        """
        for hand in self.hand_id_list:
            for p in self.task_model_list.values():
                t = eigenhand_db_objects.Task(task_id = [], #set automatically
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
        """@brief Get the grasps for this generation
        """
        return self.interface.load_grasps_for_generation(self.generation, True)

    def get_sorted_grasps(self):
        """@brief Get the grasps as a list of lists of grasps for each hand.
        """
        return get_grasps_by_hand(self.interface.load_grasps_for_generation(self.generation, True))

    def get_all_top_sorted_grasps(self, number_grasps_per_object):
        """@brief Get the grasps as a dictionary of the top n grasps for each hand,
           with the hand_ids as the keys.
        """
        return get_top_grasps_by_hand(self.interface.load_grasps_for_generation(self.generation, True),
                                      number_grasps_per_object)

    def finished(self):    
        """
        @brief Test if the current generation has finished running
        """
        self.task_list = self.interface.get_data_obj_by_index_list(Task, "task", "hand_id", self.hand_id_list)
        return not len([t for t in self.task_list if t.task_outcome_id  < 3])

    def start_generation(self):
        """
        @brief Prepare the database for the current generation
        """
        self.load_hands()
        self.insert_tasks()
#        send_condor_jobs()

    def next_generation(self):
        """
        @brief start the next generation
        """
        self.generation += 1
        self.start_generation()
