    def load_analysis_schema(interface, base_directory = '/data', experiment_name="default"):
        interface.reset_database(schema="analysis")
        interface.restore_state(experiment_name=experiment_name,schema="analysis")
        generations = interface.get_generations(experiment_name=experiment_name,schema="analysis")
        last_gen = generations[0]['id']
        interface.incremental_restore(generation = last_gen, \
            base_directory = base_directory, experiment_name = experiment_name, schema="analysis")
        for generation in generations[1:]:
            interface.incremental_restore(generation = generation['id'], tables=['grasp'], \
                base_directory = base_directory, experiment_name = experiment_name, schema="analysis")
