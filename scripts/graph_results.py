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

def load_results(experiment_name):
    interface = eigenhand_db_interface.EGHandDBaseInterface('eigenhanddb_view')
    interface.load_for_analysis(experiment_name=experiment_name)
    config = interface.load_config()
    task_model_list = task_models.model_set(config['task_models'])
    em = experiment_manager.ExperimentManager(config,task_model_list,interface=interface)
    print "%s loaded into eigenhanddb_view"%experiment_name
    return em

def output_results(experiment_name):
    em = load_results(experiment_name)

    def add_to_zip(mat, filename, zf):
        numpy.savetxt('/tmp/' + filename,mat,delimiter=',')
        zf.write('/tmp/' + filename, filename)
        os.remove('/tmp/' + filename)
    experiment_name = em.config['name']
        
    em.gm = em.initialize_generation_manager()

    #Open a zip file to put results in
    zip_file_name = '/var/www/eigenhand_project/' + experiment_name + '_csv.zip'
    zf = zipfile.ZipFile(zip_file_name,'w')

    #Create data structures for storing results
    e_list = dict()
    total_score_array = None

    print "Starting score calculation"

    #Iterate over generations calculating the scores
    for gen in xrange(em.interface.get_max_hand_gen() + 1):
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
        hands = em.interface.load_hands_for_grasps(grasp_list)

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
    output_frontend_report(em,'5 object 100000 steps 5 tasks/object 1 atr/gen 10 gen, ', total_score_array)



def output_frontend_report(em, description = '', score_array = None):
    #Write current results to the web side of things
    
    template = open('/var/www/eigenhand_project/experiment_results_template.html','r')
    template_string = template.read()
    experiment_name = em.config['name']
    output_string = template_string%(experiment_name, description,
                                     experiment_name,
                                     experiment_name,
                                     experiment_name,
                                     experiment_name,
                                     experiment_name)
    output_file = open('/var/www/eigenhand_project/%s_results.html'%(experiment_name),'w')
    output_file.write(output_string)
    template.close()
    output_file.close()
    directory_file_writer = open('/var/www/eigenhand_project/experiment_results.html','a')
    directory_file_reader = open('/var/www/eigenhand_project/experiment_results.html','r')
    new_results_string = '<a href=%s_results.html> %s </a><p>\n'%(experiment_name, experiment_name)
    if directory_file_reader.read().find(new_results_string) < 0:
        directory_file_writer.write(new_results_string)
    directory_file_writer.close()
    directory_file_reader.close()
    if score_array is not None:
        examine_database.plot_elist_vs_gen(score_array,'/var/www/eigenhand_project/%s'%(experiment_name))
                            
        
        
