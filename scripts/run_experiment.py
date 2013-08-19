
import eigenhand_db_interface
import experiment_manager
import task_models
import eigenhand_db_objects
import ate


def start_experiment(num_ga_iters = 2, num_atr_iters = 2, trials_per_task = 5, experiment_name = 'default'):
    interface = eigenhand_db_interface.EGHandDBaseInterface()

    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.full_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_ATE_hand, interface, experiment_name)
    em.kill_existing()
    interface.prepare_gen_0()

    em.run_experiment()


