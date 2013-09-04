
import eigenhand_db_interface
import experiment_manager
import task_models
import eigenhand_db_objects
import eigenhand_db_tools
import ate
import examine_database
import zipfile
import numpy
import os
import pdb

def start_experiment(num_ga_iters = 50, num_atr_iters = 5, trials_per_task = 5, experiment_name = 'eigenhand_ate_threshold_3_object'):
    interface = eigenhand_db_interface.EGHandDBaseInterface()

    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.small_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_threshold_ATE_hand, interface, experiment_name = experiment_name)
    
    print 'clearing old database'
    try:
        interface.prepare_gen_0()
    except:
        em.kill_existing()
        interface.prepare_gen_0()
    print 'starting experiment'
    em.run_experiment()
    em.restore_to_new_dbase()
    output_results(em)
    
    return em

def output_experiment(num_ga_iters = 5, num_atr_iters = 1, trials_per_task = 5, experiment_name = 'gen_0_sanity_test'):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 6000)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.small_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_threshold_ATE_hand, interface, experiment_name = experiment_name)
    em.restore_to_new_dbase()
    output_results(em)
    

def continue_experiment(num_ga_iters = 50, num_atr_iters = 5, trials_per_task = 5, experiment_name = 'default'):
    
    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.small_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_threshold_ATE_hand, [], experiment_name = experiment_name)

    #em.kill_existing()
    em.db_interface = eigenhand_db_interface.EGHandDBaseInterface()
    print 'killed existing \n'
    em.restore_all()
    print 'restored grasps \n'
    em.run_experiment()
    print 'ran experiment \n ' 
    em.restore_all()


def restore_experiment(num_ga_iters = 50, num_atr_iters = 5, trials_per_task = 5, experiment_name = 'eigenhand_ate_threshold'):
    interface = eigenhand_db_interface.EGHandDBaseInterface()

    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.small_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_threshold_ATE_hand, interface, experiment_name = experiment_name)
    em.restore_to_new_dbase()



def test_output_results(num_ga_iters = 50, num_atr_iters = 5, trials_per_task = 5, experiment_name = 'eigenhand_ate_threshold'):
    interface = eigenhand_db_interface.EGHandDBaseInterface(experiment_name)

    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.small_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_threshold_ATE_hand, interface, experiment_name = experiment_name)

    output_results(em)

def output_results(em):
    def add_to_zip(mat, filename, zf):
        numpy.savetxt('/tmp/' + filename,mat,delimiter=',')
        zf.write('/tmp/' + filename, filename)
        os.remove('/tmp/' + filename)
    experiment_name = em.experiment_name
        
    em.initialize_generation_manager()

    #Open a zip file to put results in
    zip_file_name = '/var/www/eigenhand_project/' + experiment_name + '_csv.zip'
    zf = zipfile.ZipFile(zip_file_name,'w')

    #Create data structures for storing results
    e_list = dict()
    total_score_array = None

    #Iterate over generations calculating the scores
    for gen in xrange(em.db_interface.get_max_hand_gen() + 1):
        print gen
        #Set current generation
        em.gm.generation = gen

        #get updated grasps for genetaion
        grasp_list = em.gm.get_all_grasps()        
        
        #get a list of only the top grasps by grasp force optimization score.
        top_grasp_dict = experiment_manager.generation_manager.get_top_grasps_by_hand(grasp_list, 10)
        top_grasp_list = []
        [top_grasp_list.extend(gl) for gl in top_grasp_dict.values()]

        #Load the hands for the relevant grasps. This gets only those hands for this generation that were valid enough to produce grasps
        hands = em.db_interface.load_hands_for_grasps(grasp_list)

        em.gm.hands = hands

        #Get the numpy matrix of the grasps, top grasps, and hands
        grasp_mat = eigenhand_db_tools.output_grasps_mat(grasp_list)
        top_grasp_mat = eigenhand_db_tools.output_grasps_mat(top_grasp_list)
        hand_mat = eigenhand_db_tools.output_hands_mat(em.gm.hands, gen)

        #Re analyze the hands to get all of the relevant scores
        e_list = examine_database.get_e_list(em.gm, [], em.eval_functor)
        score_array = numpy.array([[e_list[k][0], k,e_list[k][1],numpy.sum(e_list[k][2]), numpy.sum(e_list[k][3]), e_list[k][4]] for k in e_list])
        valid_score_array = score_array[numpy.nonzero((score_array[:,2] < 500) & (score_array[:,5] < 2))]
        try:
            if total_score_array is not None:
                total_score_array = numpy.vstack([total_score_array, valid_score_array])
            else:
                total_score_array = valid_score_array
                
            hand_mat = numpy.hstack([hand_mat, score_array[:,2:]])
        except:                
                pdb.set_trace()

        #output the matrices to a csv file.
        add_to_zip(top_grasp_mat,'%s_top_grasp_gen_%i.csv'%(experiment_name,gen), zf)
        add_to_zip(grasp_mat,'%s_grasp_gen_%i.csv'%(experiment_name,gen), zf)
        add_to_zip(hand_mat,'%s_hand_gen_%i.csv'%(experiment_name,gen), zf)

    

    #close the zip file
    zf.close()  

    #Write current results to the web site
    output_frontend_report(em,'weighted threshold ate with one object (drill) 50 generations', total_score_array)



def output_frontend_report(em, description = '', score_array = None):
    #Write current results to the web side of things
    
    template = open('/var/www/eigenhand_project/experiment_results_template.html','r')
    template_string = template.read()
    output_string = template_string%(em.experiment_name, description,
                                     em.experiment_name,
                                     em.experiment_name,
                                     em.experiment_name,
                                     em.experiment_name,
                                     em.experiment_name)
    output_file = open('/var/www/eigenhand_project/%s_results.html'%(em.experiment_name),'w')
    output_file.write(output_string)
    template.close()
    output_file.close()
    directory_file_writer = open('/var/www/eigenhand_project/experiment_results.html','a')
    directory_file_reader = open('/var/www/eigenhand_project/experiment_results.html','r')
    new_results_string = '<a href=%s_results.html> %s </a>\n'%(em.experiment_name, em.experiment_name)
    if directory_file_reader.read().find(new_results_string) < 0:
        directory_file_writer.write(new_results_string)
    directory_file_writer.close()
    directory_file_reader.close()
    if score_array is not None:
        examine_database.plot_elist_vs_gen(score_array,'/var/www/eigenhand_project/%s'%(em.experiment_name))
                            
        
        
