import time
import os

import remote_dispatcher,  generation_manager
import eigenhand_db_interface, eigenhand_db_tools, eigenhand_db_objects
import atr, ate
import eigenhand_genetic_algorithm
import task_models, server_list
import examine_database

class ExperimentManager(object):
    def __init__(self, config, task_model_list,
                 eval_functor = ate.weighted_threshold_ATE_hand,
                 server_dict = server_list.clic_lab_dict,
                 task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = -1),
                 interface = eigenhand_db_interface.EGHandDBaseInterface()):
        """
        @param num_ga_iters - The number of genetic algorithm generations to run
        @param num_atr_iters - The number of ATR iterations to run for each GA generation
        @param task_model_list - A list of TaskModels used to set up the database planner
        @param task_prototype - A prototype Task object that defines the trial specification(i.e. length and type)
        @param trials_per_task - The number of planning jobs to run for each object/hand pair per planning iteration. Results from each should look fairly unique.
        @param eval_functor - The function to use when evaluating hand fitness in the genetic algorithm
        @param interface - The database interface to use. Assumed to be initialized with a starting set of 0th generation hands
        @param starting_ga_iter - The generation to start from.
        @param server_dict - A dictionary whose keys are server urls that will be filled with
                             Servers as connections are made
        """
        self.task_prototype = task_prototype
        self.task_model_list = task_model_list
        self.eval_functor = eval_functor
        self.interface = interface
        self.config = config
        self.server_dict = server_dict
        self.e_list = dict()

        self.gm = []
        self.rd = []       #self.score_array = numpy.array([4,0])
        

    def initialize_generation_manager(self):
        """
        @brief Create the generation manager that will be used in this experiment
        """
        return generation_manager.GenerationManager(self.interface, self.task_model_list,
                                                    self.interface.get_max_hand_gen(),
                                                    self.config['task_time'], self.config['trials_per_task'],
                                                    self.config['task_type_id'],
                                                    self.eval_functor)


    def output_current_status(self):
        filename = '/var/www/eigenhand_project/results'
        self.e_list.update(examine_database.get_e_list(self.gm, [], self.eval_functor))
        score_array = examine_database.e_list_to_score_array(self.e_list)
        examine_database.plot_elist_vs_gen(score_array, filename)


    def run_remote_dispatcher_tasks(self):
        """
        @brief Run the tasks on a cluster using the RemoteDispatcher framework developed for this project.

        """
        #Record the start time
        t = time.time()
        r = 0
        #Test if there are jobs available to do.
        job_num = eigenhand_db_tools.get_num_unlaunched_jobs(self.interface)

        #Try to run a new remote dispatcher loop as long as there are unfinished jobs
        while job_num > 2:
            print "Starting Dispatcher Assignment Loop %s"%r
            r += 1
            #Blocks until time runs out or all jobs are finished.
            self.rd.run()
            #Reset any incomplete jobs. These are essentially jobs that we have lost connection with and cannot be
            #relied upon to terminate.
            self.interface.reset_incompletes()
            #See how many jobs are still undone.
            job_num = eigenhand_db_tools.get_num_unlaunched_jobs(self.interface)
        #If we only have a few stragglers, just stop trying -- We don't really need all of them to exit cleanly,
        #and it is easier to fail gracefully than try to handle every error.
        self.interface.set_incompletes_as_error()
        print "done.  Time %f \n"%(time.time() - t)

    def backup_results(self):
        self.interface.incremental_backup(experiment_name=self.config['name'],generation=self.gm.generation)
        self.interface.state_backup(experiment_name=self.config['name'])

    def restore_results(self, generation=0):
        self.interface.incremental_restore(experiment_name=self.config['name'],generation=self.gm.generation)

    def prepare_experiment(self):
        self.interface.reset_database()
        print "Working database reset"

        self.interface.update_config(self.config) 
        print "Pushed configuration to database"

        self.interface.insert_gen_0()
        print "Gen 0 fingers, hands and grasps inserted"

        #initialize new generation manager to configure the database to start running.
        self.gm = self.initialize_generation_manager()
        self.gm.next_generation(gen_type=0)
        print "Generation manager initialized at generation %i"%self.gm.generation

        #Build the new remote dispatcher and connect all the servers
        self.rd = remote_dispatcher.RemoteDispatcher(self.interface)
        print "Remote dispatcher initialized"
        self.rd.init_all_servers(self.server_dict)
        print "Clustering servers started"
        

    def run_experiment(self):
        """
        @brief Run the whole experiment. Does num_ga_iters genetic algorithm runs each containing num_atr iterations
        of ATR.
        """

        #Run through a bunch of iterations
        generations = ([1]*self.config['atr_iterations'] + [2])*self.config['ga_iterations']
        print "%s generations: {%s}"%(len(generations),', '.join(str(generation) for generation in generations))

        #Start it up
        print "Running vanilla generation 0"
        self.run_remote_dispatcher_tasks()
        print "Generation %i complete"%self.gm.generation

        for generation,gen_type in enumerate(generations,1):
            #Get the resulting grasps for the latest generation of hands
            grasp_list = self.gm.get_all_grasps()
            #self.output_current_status()

            #Every num_atr_iters+1th iteration is a genetic swap
            if gen_type == 1:
                #Run atr on the existing hand for the latest generation of grasps
                new_hand_list = atr.ATR_generation(grasp_list, self.gm.hands)
                print "New hands generated through ATR on the results of generation %i"%self.gm.generation
            elif gen_type == 2:
                #Generate new hands based on these grasps, scaling the variance of the mutations down linearly as the
                #generations progress.
                new_hand_list = eigenhand_genetic_algorithm.GA_generation(grasp_list, self.gm.hands, self.eval_functor, .5-.4/(self.config['ga_iterations']*generation/(1+self.config['atr_iterations'])))
                print "New hands generated through genetic algorithm on the results of generation %i"%self.gm.generation

            #Put the new hands in to the database.
            eigenhand_db_tools.insert_unique_hand_list(new_hand_list, self.interface)

            #Backup results and then remove everything from the grasp table
            self.backup_results()
            self.interface.clear_tables(['grasp','job'])

            print "Backed up and reset for new generation"

            #Run the planner to get grasps for the last set of hands
            self.gm.next_generation(gen_type=gen_type)
            print "Starting generation %i"%self.gm.generation

            #Run the planning jobs
            self.run_remote_dispatcher_tasks()
            print "Finished generation %i"%self.gm.generation


        self.backup_results()
        print "Backed up final results"

        self.rd.kill_all_servers()
        print "Killed all servers"

    def run(self):
        self.prepare_experiment()
        print "Experiment set up"
        self.run_experiment()
        print "Experiment finished"

def new_em(name, ga_iterations, atr_iterations = 5, task_model_names = task_models.tiny_keys):
    config = {'name':name,
              'ga_iterations':ga_iterations,
              'atr_iterations':atr_iterations,
              'trials_per_task':5,
              'task_type_id': 4,
              'task_time': -1,
              'task_models':task_model_names}
    task_model_list = task_models.model_set(task_model_names)
    em = ExperimentManager(config,task_model_list)
    return em

def resume_em():
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    config = interface.load_config()
    task_model_list = task_models.model_set(config['task_models'])
    em = ExperimentManager(config,task_model_list,interface=interface)
    return em

def restart_servers(server_dict = server_list.clic_lab_dict):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    rd = remote_dispatcher.RemoteDispatcher(interface)
    rd.init_all_servers(server_dict)
