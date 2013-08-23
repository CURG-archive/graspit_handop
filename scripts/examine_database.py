import numpy
import pylab
import grasp_sorting_utils
import ate





def get_e_list(gm = [], generation_num = []):
    if not gm:
        interface = EGHandDBaseInterface()        
        gm = GenerationManager(interface, task_model_list, generation_num, 15, 5, 4, ATE_hand)
        gm.get_all_grasps()

    grasp_dict = grasp_sorting_utils.get_top_grasps_by_hand(gm.grasp_list, 10)
    
    e_list = dict()
    for key in grasp_dict:
        if not grasp_dict[key]:
            continue
        e_list[key] = [gm.generation] + list(ate.get_all_scores(grasp_dict[key], [h for h in gm.hands if h.hand_id == key][0]))
        
    return e_list

def get_generation_score_array(gm):
    e_list = get_e_list(gm)
    score_array = e_list_to_score_array(e_list)
    return score_array

def e_list_to_score_array(e_list):
    #[generation_num, hand_id, top_mean_hand_score, digit_coupling_complexity, actuator_complexity]
    return numpy.array([[e_list[k][0], k,e_list[k][1],numpy.sum(e_list[k][2]), numpy.sum(e_list[k][3])] for k in e_list.keys()])





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



def rescale_view():
    pylab.gca().yaxis.zoom(-1)
    pylab.gca().xaxis.zoom(-1)

def plot_poly_fit(x,y):
    (m,b) = pylab.polyfit(x,y,1)
    xp = numpy.unique(x)
    yp = pylab.polyval([m,b],xp)
    pylab.plot(xp, yp)
    
def plot_elist_vs_gen(score_array, base_filename = None):
    pylab.clf()
    pylab.hold(True)
    pylab.plot(score_array[:,0], score_array[:,2],'.')
    plot_poly_fit(score_array[:,0], score_array[:,2])
    rescale_view()
    pylab.savefig(base_filename + '_grasp_energy.png')
    pylab.clf()
    pylab.hold(True)
    pylab.plot(score_array[:,0], score_array[:,3],'.')
    plot_poly_fit(score_array[:,0], score_array[:,3])
    
    rescale_view()
    pylab.savefig(base_filename + '_coupling_complexity.png')
    pylab.clf()
    pylab.hold(True)
    pylab.plot(score_array[:,0], score_array[:,4],'.')
    plot_poly_fit(score_array[:,0], score_array[:,4])
    
    rescale_view()
    pylab.savefig(base_filename + '_actuator_complexity.png')
    pylab.clf()
    final_score = score_array[:,2]* (score_array[:,3]*.4 + score_array[:,4] * .6)
    pylab.plot(score_array[:,0],final_score , '.')
    plot_poly_fit(score_array[:,0],final_score)
    rescale_view()
    pylab.savefig(base_filename + '_ate_score.png')
    
    
        
        
    


def plot_total_score(score_array):
    pylab.plot(score_array[:,0], score_array[:,2]*(.4*score_array[:,3] + .6*score_array[:,4]))

