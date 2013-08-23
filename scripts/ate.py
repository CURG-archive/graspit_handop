from numpy import *



def princomp(A,numpc=0):
    """
    @brief Perform PCA on matrix A

    @param A - The matrix to perform PCA on
    @param numpc - The number of principle components to find.

    @returns coeff - The principle components
    @returns latent - The strength of each component
    @returns score - The projection of the old matrix in to the principal components space.

    """
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



def mean_top_grasps(grasp_list, grasp_num=10):
    """
    @brief Get the mean energy of the top grasps.

    @param grasp_list - The grasps to analyze
    @param grasp_num - The number of grasps to allow
    """
    grasp_list.sort(key=lambda a:a.grasp_energy)
    return mean(array([g.grasp_energy for g in grasp_list[:grasp_num]]))


def calculate_ATE_scores(grasp_list, hand):
    """
    @brief Calculate the complexity of the hand's actuation.

    Calculate the complexity of the hand's actuation. This score rewards hands whose grasps can
    be described well by the fewest number of principle components. It is calculated as the combination
    of two scores, digit coupling complexity and actuation complexity.
    
    The digit coupling complexity tries quantify how complex a mechanical linkage is necessary to drive
    each finger independently, in a conceptual way. It takes the principle components of the finger
    positions of each finger and looks at how many times consecutive joints would have to go in opposite
    directions.
    
    The actuation complexity counts the number of eigenvectors that have strong influence on each finger.
    To do this, it counts the number of eigenvectors for which each finger has any entry above some threshold.
    """
    
    def get_digit_coupling_complexity(finger_actuation_vector):
        return sum(abs(diff(finger_actuation_vector)))


    def get_grasp_joints(grasp_list):
        """
        @brief Translate a list of grasps into a matrix of grasp joints, where each row is the joint
        locations of a single grasp.
        
        @param grasp_list - The list of grasps to matrixify.
        """
        return array([g.grasp_grasp_joints for g in grasp_list])*(180.0/pi)

    def get_indices_for_finger(hand, finger_num):
        """
        @brief Get the indices in to a grasp vector that represent joints on a particular finger.
        
        @param hand - The hand to get the index in to
        @param finger_num - The finger to use.
        
        @returns [start_index, end_index] such that grasp_vector[start_index:end_index] gives you the
        joint positions for the selected finger.
        """
        finger_start_ind = sum([len(finger.link_length_list) for finger in hand.fingers[:finger_num]])
        finger_end_ind = finger_start_ind + len(hand.fingers[finger_num].link_length_list)
        return finger_start_ind, finger_end_ind
        
    def get_finger_joints(hand, finger_num, grasp_joint_array):
        """
        @brief Get the joint position matrix for a particular finger from a matrix of grasps
        
        @param hand - The Hand from which these grasps are derived.
        @param finger_num - The number of the finger selected
        @param grasp_joint_array - The array of grasp joints.
        
        @returns a matrix of joint positions from the grasps.
        """
        finger_start_ind, finger_end_ind = get_indices_for_finger(hand, finger_num)
        return grasp_joint_array[:,finger_start_ind:finger_end_ind]
    
    def get_truncated_eigenvectors(grasp_joint_array, capture_ratio):
        """
        @brief Get the top most relevant grasps
        
        @param grasp_joint_array - A matrix of grasps
        @param capture_ratio - The fraction of principle components to capture
        
        @returns The principal components of the grasp joint array that explain
        the request fraction of the variability.
        """
        coeff,score,latent = princomp(grasp_joint_array)
        return coeff[:,nonzero(cumsum(latent/sum(latent)) >= capture_ratio)]

    def get_coupling(eigenvector, relevance_ratio):
        """
        @brief Get a boolean vector of the joints that are strongly coupled.
        
        @param eigenvector - the eigenvector being analyzed
        @param relevance_ratio - The threshold at which a component is considered strong
        
        @returns a boolean vector with 1 for each strong component and a 0 for each weak component.
        """
        return(fabs(eigenvector > relevance_ratio))
               
    #translate the grasp list in to a matrix of grasps
    grasp_joints = get_grasp_joints(grasp_list)
    #Get the eigenvectors that represent the top 90% of variance of the grasp list
    eigenvectors = get_truncated_eigenvectors(grasp_joints, .9)

    #Figure out the number of eigenvectors
    num_cols = eigenvectors.shape[2]
               
    num_fingers = len(hand.fingers)

    digit_coupling_complexity = zeros([num_cols, num_fingers])
    
    #Calculate the digit coupling complexity by iterating over the eigenvectors
    for e_ind in range(num_cols):
        #The eigenvector matrix comes out with an extra, degenerate dimension.
        #Pull the real eigenvector out.
        eigenvector = eigenvectors[:,0,e_ind]

        #Iterate over each fingers joints independently
        for f_ind in range(num_fingers):

            #Get the relevant indices for the finger we are examining.
            start_ind, end_ind = get_indices_for_finger(hand, f_ind)

            #Get the coupling vector for this finger
            coupling = get_coupling(eigenvector[start_ind: end_ind], .2)

            #Add the coupling complexity for this finger to the coupling complexity matrix
            digit_coupling_complexity[e_ind, f_ind] = get_digit_coupling_complexity(coupling)    


    #Now calculate the actuator complexity
    actuator_complexity = zeros([1,num_fingers])

    #This time we iterate over fingers first
    for f_ind in range(num_fingers):
        for e_ind in range(num_cols):
            #Get the start and end indices for this finger
            start_ind, end_ind = get_indices_for_finger(hand, f_ind)
            #Get the part of the current eigenvector relevant to this finger
            eigenvector = eigenvectors[start_ind:end_ind,0,e_ind]
            #If any of the eigenvector's components are strong enough, add one
            #to the number of actuators required for this finger. 
            actuator_complexity[0,f_ind] += any(eigenvector > .2)

    #hand.energy_list = [digit_coupling_complexity, actuator_complexity]
    return digit_coupling_complexity, actuator_complexity

def ATE_hand(grasp_list, hand, alpha = .4, beta = .6):
    """
    @Calculates the combined ATE score for the hand

    @param grasp_list - The grasps to consider
    @param hand - The Hand that we are calculating the score for
    @param alpha - The weight of the digit_coupling_complexity in the final score
    @param beta - The weight of the actuator complexity in the final score

    @returns a float that measures the complexity of the hand. Higher is more complex.
    """
    digit_coupling_complexity, actuator_complexity = calculate_ATE_scores(grasp_list, hand)
    return alpha*sum(sum(digit_coupling_complexity))*beta*sum(actuator_complexity)


def weighted_ATE_hand(grasp_list, hand):
    tmh = mean_top_grasps(grasp_list)
    if tmh < 0:
        tmh = -tmh
        #    else:
        #        print "hand %d mean energy > 0 "%(hand.hand_id)
        #        print tmh
        
    return tmh * ATE_hand(grasp_list, hand)


def get_all_scores(grasp_list, hand):
    tmh = mean_top_grasps(grasp_list)
    if tmh < 0:
        tmh = -tmh
        #    else:
        #        print "hand %d mean energy > 0 "%(hand.hand_id)
        #        print tmh
    digit_coupling_complexity, actuator_complexity = calculate_ATE_scores(grasp_list, hand)
    return tmh, digit_coupling_complexity, actuator_complexity

def calculate_digit_coupling_complexity(grasp_list, hand):
    return calculate_ATE_scores(grasp_list, hand)[0]


            
def test_ATE():
    interface = EGHandDBaseInterface()
    task_model_list = [model_dict['hammer']]
    gm = GenerationManager(interface,
                           task_model_list,
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
