from eigenhand_automation import *
import numpy
import pylab

def get_e_list(generation_num, interface = []):
    if not interface:
        interface = EGHandDBaseInterface()
    task_prototype_list = [model_dict['hammer']]
    gm = GenerationManager(interface, task_prototype_list, generation_num, 15, 5, 4, ATE_hand)
    gm.load_hands()
    if not gm.hands:
        raise Exception()
    grasp_dict = gm.get_all_top_sorted_grasps(10)

    e_list = dict()
    for key in grasp_dict:
        e_list[key] = [generation_num] + list(get_all_scores(grasp_dict[key], [h for h in gm.hands if h.hand_id == key][0]))


            
        
    return e_list


def e_list_to_score_array(e_list):
    %[generation_num, hand_id, top_mean_hand_score, digit_coupling_complexity, actuator_complexity]
    return numpy.array([[e_list[k][0], k,e_list[k][1],sum(e_list[k][2]), sum(e_list[k][3])] for k in e_list.keys()])





def get_all_generations():
    e_list = dict()    
    num_generations = 300
    interface = EGHandDBaseInterface()
    for i in xrange(num_generations):
        try:
            e_list.update(get_e_list(i,interface))
        except:
            break
    return e_list_to_score_array(e_list)




    
def plot_elist_vs_gen(score_array):
    pylab.plot(score_array[:,0], score_array[:,1],'.')
    pylab.plot(score_array[:,0], score_array[:,2],'.')
    pylab.plot(score_array[:,0], score_array[:,3],'.')
    pylab.plot(score_array[:,0], score_array[:,4],'.')
    pylab.show()


def plot_total_score(score_array):
    pylab.plot(score_array[:,0], score_array[:,2]*(.4*score_array[:,3] + .6*score_array[:,4]))
