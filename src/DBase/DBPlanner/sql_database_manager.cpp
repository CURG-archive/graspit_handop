//######################################################################
//
// GraspIt!
// Copyright (C) 2002-2009  Columbia University in the City of New York.
// All rights reserved.
//
// This software is protected under a Research and Educational Use
// Only license, (found in the file LICENSE.txt), that you should have
// received with this distribution.
//
// Author(s):  Corey Goldfeder
//
// $Id: sql_database_manager.cpp,v 1.17 2009/07/22 17:59:32 coreyg Exp $
//
//######################################################################

/*! \file 
    \brief Defines members of the %SqlDatabaseManager class
 */


#include "sql_database_manager.h"

#include <sstream>
#include <vector>
#include <cmath>
#include <QHostInfo>
using std::make_pair;    // Included from <utility> in "db_manager.h"
using std::stringstream;
using std::vector;

#include <iostream>
using namespace std;

//#define PROF_ENABLED
#include "profiling.h"
#include "debug.h"

#include "eigenhand_db_interface.h"

PROF_DECLARE(GET_GRASPS_SQL);
PROF_DECLARE(GET_GRASPS_GETCOLUMN);
PROF_DECLARE(GET_GRASPS_GETFIELD);

namespace db_planner {

bool SqlDatabaseManager::GetAlignment(const Model& source,
                                      const Model& dest, 
                                      const string& alignment_method_name, 
                                      float alignment[16]) const {
  Table results;
  stringstream query_text;                  
  query_text << "SELECT get_alignment('" << source.ModelName() << "','" 
             << dest.ModelName() << "','" << alignment_method_name << "')";
  if (!database_.QueryAndConnect(query_text.str(), &results)) return false;
  vector<float> alignment_vector;
  alignment_vector.reserve(16);
  if (results.NumColumns() == 0 || results.NumRows() == 0) return false;
  if (!results.GetField(0, 0, &alignment_vector)) return false;
  for (int i = 0; i < 16; ++i) alignment[i] = alignment_vector[i];
  return true;
}

bool SqlDatabaseManager::SaveAlignment(const Model& source,
                                       const Model& dest, 
                                       const string& alignment_method_name, 
                                       const float alignment[16]) const {
  if (alignment[0] == 0) return false;
  if (alignment_method_name == "") return false;
  if (source.ModelName() != dest.ModelName()) return false;
  return false;
}


//! Load a Model from the database and populate its fields.
class LoadModelFunctor {
 private:
  const Table& table_;
  const string& model_root_;
  int model_name_column_, thumbnail_path_column_, scale_column_, 
    tags_column_, grasping_rescale_column_, geometry_path_column_, symmetry_axis_column_;
  bool initialized_;
 public:
   LoadModelFunctor(const Table& table, const string& model_root) 
       : table_(table), model_root_(model_root) {
     initialized_ = 
       table_.GetColumnIndex("scaled_model_name", &model_name_column_) &&
       table_.GetColumnIndex("original_model_thumbnail_path", &thumbnail_path_column_) &&
       table_.GetColumnIndex("original_model_geometry_path", &geometry_path_column_) &&
       table_.GetColumnIndex("scaled_model_scale", &scale_column_) &&
       table_.GetColumnIndex("original_model_tags", &tags_column_) &&
       //table_.GetColumnIndex("symmetry_axis", &symmetry_axis_column_) &&
       table_.GetColumnIndex("original_model_grasping_rescale", &grasping_rescale_column_);         
   }
  bool operator()(Model* model, const int row) {
    string model_name, thumbnail_path, geometry_path;
    double scale, grasping_rescale;
    vector<string> tags;
    vector<double> symmetry_axis;
    if (!initialized_ ||
        !table_.GetField(model_name_column_, row, &model_name) || 
        !table_.GetField(thumbnail_path_column_, row, &thumbnail_path) ||
        !table_.GetField(geometry_path_column_, row, &geometry_path) ||
        !table_.GetField(scale_column_, row, &scale) ||
        !table_.GetField(tags_column_, row, &tags) ||
	//!table_.GetField(symmetry_axis_column_, row, &symmetry_axis) ||
        !table_.GetField(grasping_rescale_column_, row, &grasping_rescale))
      return false;
    model->SetModelName(model_name);
    model->SetThumbnailPath(model_root_ + thumbnail_path);
    model->SetScale(scale);
    model->SetTags(tags.begin(), tags.end());
    model->SetGeometryPath(model_root_ + geometry_path);
    model->SetRescaleFactor(grasping_rescale * scale);
    //    model->SetSymmetryAxis(symmetry_axis.begin(), symmetry_axis.end());
    return true;
  }
};



bool SqlDatabaseManager::GetNeighbors(const Model& model, 
                                      const string& distance_function_name, 
                                      const int num_neighbors,
                                      vector<pair<Model*, double> >* neighbors) const {
  if (neighbors == NULL) return false;
  Table results;
  stringstream query_text;                  
  query_text << "SELECT * FROM get_saved_neighbors('" << model.ModelName()
             << "','" << distance_function_name 
             << "'," << num_neighbors << ");";
  if (!database_.QueryAndConnect(query_text.str(), &results)) return false;
  int distance_column;
  if (!results.GetColumnIndex("distance", &distance_column)) return false;
  // Turn each database row into a Model.
  LoadModelFunctor load_model_functor(results, model_root_);
  double distance;
  const int num_rows = results.NumRows();
  neighbors->reserve(num_rows);
  for (int row = 0; row < num_rows; ++row) {
    Model* neighbor_model = model_allocator_->Get();
    if (!load_model_functor(neighbor_model, row) ||
        !results.GetField(distance_column, row, &distance)) return false;
    neighbors->push_back(make_pair(neighbor_model, distance));
  }
  return true;
}

bool SqlDatabaseManager::SaveNeighbors(
    const Model& model, 
    const string& distance_function_name, 
    const vector<pair<Model*, double> >& neighbors) const {
  if (model.ModelName() == "") return false;
  if (distance_function_name == "") return false;
  if (&neighbors == NULL) return false;
  return false;
}

bool SqlDatabaseManager::GetNextTask(TaskRecord *rec, const string & requestedStatus, const string & setStatus) {
	Table result;
	//in one fell swoop:
	//get a task with the desired status from the list
	//get the data needed to initialize a model
	//and get the name of the hand as well

	//for now we hard-code desired task status
	string status(requestedStatus);
	bool succeeded = true;
	database_.DBOpen();
	//start transaction
	if (!database_.Query("START TRANSACTION ISOLATION LEVEL READ COMMITTED;", NULL))
		succeeded = false;
	std::string querystring = "SELECT * FROM task JOIN scaled_model USING(scaled_model_id) JOIN hand USING(hand_id) JOIN task_outcome USING(task_outcome_id) JOIN original_model USING(original_model_id) WHERE '" +status +"'=task_outcome_name AND task_type_id = " + QString::number(rec->taskType).toStdString() + " LIMIT 1 FOR UPDATE;";
	std::cout<<querystring <<std::endl;
	if(!succeeded || !database_.Query(querystring,&result)) {
		//we have no way of knowing if the query is wrong, or
		//there are simply no entries not marked "complete" in the task table
		//we assume the latter
		rec->taskType = 0;
		return succeeded; 
	}
	//get the model
	LoadModelFunctor load_model_functor(result, model_root_);
	Model *model = model_allocator_->Get();
	if (!load_model_functor(model, 0)) {
		//std::cout << "load model failed\n";
		succeeded = false;
	}
	rec->model = model;
	//get the hand name and task type
	int hand_col, type_col, id_col, time_col, misc_col, param_col, hand_id_col;
	if (!succeeded || !result.GetColumnIndex("hand_name", &hand_col) ||
	    !result.GetColumnIndex("task_type_id", &type_col) ||
	    !result.GetColumnIndex("task_time", &time_col) ||
	    !result.GetColumnIndex("task_id", &id_col) ||
	    !result.GetColumnIndex("hand_id", &hand_id_col)) {
		//std::cout << "get column failed\n";
		succeeded = false;
	}
	if (! succeeded || !result.GetField(hand_col, 0, &(rec->handName)) || 
	    !result.GetField(type_col, 0, &(rec->taskType)) || 
	    !result.GetField(time_col, 0, &(rec->taskTime)) || 
	    !result.GetField(id_col, 0, &(rec->taskId)) || 
	    !result.GetField(hand_id_col, 0, &(rec->handId))
	    ) {
		//std::cout << "get record failed\n";
		succeeded = false;
	}
	if(result.GetColumnIndex("comment", &misc_col)){
	  result.GetField(misc_col, 0, &(rec->misc));
	}
	else {
	  rec->misc = "unused";
	}
	
	if(result.GetColumnIndex("parameters", &param_col)){
	  result.GetField(param_col, 0, &(rec->params));
	}


	//if we have so far been successful, and the current task status is not the requested task status, change
	//the requested task status
	if (!succeeded || (requestedStatus.compare(setStatus) && !SetTaskStatus(*rec, setStatus, false)))
		succeeded = false;
	//always attempt to commit the transaction, just in case we succeeded at starting the transaction somewhere
	if(!database_.Query("COMMIT TRANSACTION;", NULL)){
		DBGA("Failed to release lock on commit on task_id");
		succeeded = false;
	}
	database_.DBClose();
	return succeeded;
}

bool SqlDatabaseManager::SetTaskStatus(const TaskRecord &rec, const string &status, const bool requestTransaction)
{
	Table result;
	stringstream id;
	id << rec.taskId;
	bool succeeded = true;
	//start transaction
	if (requestTransaction){
	  database_.DBOpen();
	  if(!database_.Query("START TRANSACTION ISOLATION LEVEL READ COMMITTED",NULL))
		succeeded = false;
	  //check if the entry exists in the database
	  if (!succeeded || !database_.Query("SELECT * FROM task WHERE task_id=" + id.str() + " FOR UPDATE;", &result)) {
	    DBGA("SqlDatabaseManager:SetTaskStatus:Failed to find desired task id");
	    succeeded = false;
	  }
	}
	//mark it as current status and timestamp this status
	if (!succeeded || !database_.Query("UPDATE task SET task_outcome_id=(SELECT task_outcome_id FROM task_outcome WHERE task_outcome_name='"+status+"'), task_time_stamp=NOW(), last_updater='"+QHostInfo::localHostName().toStdString().c_str()+"' WHERE task_id="+id.str()+";", NULL)) {
		DBGA("SqlDatabaseManager:SetTaskStatus:Failed to update task");
		succeeded = false;
	}
	if(requestTransaction && !database_.Query("COMMIT TRANSACTION;", NULL) && database_.DBClose()){
		DBGA("Failed to release lock on commit on task_id");
		succeeded = false;
	}
	return succeeded;
}

bool SqlDatabaseManager::AgeTaskStatus(const int &tType, const string &currentStatus, const string & ageToStatus, int expirationTime)
{
	Table result;
	
	bool succeeded = true;
	//start transaction
	if (!database_.QueryAndConnect("START TRANSACTION ISOLATION LEVEL READ COMMITTED", NULL))
		succeeded = false;
	//Get all matching types in database
	string queryString = "UPDATE task SET task_outcome_id=(SELECT task_outcome_id FROM task_outcome where task_outcome_name='" +ageToStatus +"'), task_time_stamp = NOW(), last_updater='"+QHostInfo::localHostName().toStdString().c_str()+" :Aged' WHERE task_type_id=" + QString::number(tType).toStdString() + " AND task_outcome_id=(SELECT task_outcome_id FROM task_outcome WHERE task_outcome_name='"+currentStatus +"') AND (task_time_stamp + '" + QString::number(expirationTime).toStdString() +" seconds') < NOW();";
	DBGA(queryString);
	     if (!succeeded || !database_.QueryAndConnect(queryString, NULL)) {
		DBGA("Nothing was aged out");	
		succeeded = false;
	}
	if(!database_.QueryAndConnect("COMMIT TRANSACTION;", NULL)){
		DBGA("Failed to release lock on commit on task_id");
		succeeded = false;
	}
	return succeeded;
}

bool SqlDatabaseManager::ModelList(vector<Model*>* model_list, 
								   FilterList::FilterType filter) const {
  if (model_list == NULL) return false;
  Table results;
  if (!database_.QueryAndConnect("SELECT * FROM get_models() " + 
						FilterList::GetWhereClause(filter) + ";", 
						&results)) return false;
  // Turn each database row into a Model.
  LoadModelFunctor load_model_functor(results, model_root_);
  const int num_rows = results.NumRows();
  model_list->reserve(num_rows);
  for (int row = 0; row < num_rows; ++row) {
    Model* model = model_allocator_->Get();
	if (!load_model_functor(model, row)){
		return false;
	}
    model_list->push_back(model);
  }
  return true;
}

//! Return a list of some name_type, such as "distance_function" or "alignment_method"
/*! This is a helper to filter out duplicate code from the GetXXXList functions.
    The name_type is assumed to be the name of the table, and the column in the table
    is assumed to be "<name_type>_name".*/
static bool NameList(const string& name_type, 
                     const DatabaseConnection& database,
                     vector<string>* list) {
  if (list == NULL) return false;
  Table results;
  if (!const_cast<DatabaseConnection&>(database).QueryAndConnect("SELECT * FROM get_" + name_type + "_names();", 
      &results)) return false;
  const int num_rows = results.NumRows();
  list->reserve(num_rows);
  int name_column;
  if (!results.GetColumnIndex(name_type + "_name", &name_column)) return false;
  string name;
  for (int row = 0; row < num_rows; ++row) {
    if (!results.GetField(name_column, row, &name)) return false;
    list->push_back(name);
  }
  return true;
}

bool SqlDatabaseManager::DistanceFunctionList(
    vector<string>* distance_function_list) const {
  return NameList("distance_function", database_, distance_function_list);
}

bool SqlDatabaseManager::AlignmentMethodList(
    vector<string>* alignment_method_list) const {
  return NameList("alignment_method", database_, alignment_method_list);
}

bool SqlDatabaseManager::TaskTypeList(
	vector<string> * task_type_list) const {
  return NameList("task_type", database_, task_type_list);
					  ;
}
bool SqlDatabaseManager::GraspTypeList(
	vector<string>* type_list) const {
		return NameList("grasp_type", database_, type_list);
}

/*
bool SqlDatabaseManager::getGraspByID(QString graspID, Grasp * g){
Table result;
  if (!database_.QueryAndConnect("SELECT * FROM grasp WHERE grasp_id = " + graspID, &results)) 

}
*/

  bool SqlDatabaseManager::GetGrasps(const Model & model, 
				     const int hand_id,
				     vector<Grasp*> * grasp_list) const
  {
    if (grasp_list == NULL) return false;
  Table results;
  PROF_START_TIMER(GET_GRASPS_SQL);
  std::string commandStr = "SELECT * FROM get_grasps2('" + model.ModelName() + 
    "','" + QString::number(hand_id).toStdString() + "');";
  std::cout << commandStr << std::endl;
  
  if (!database_.QueryAndConnect(commandStr, &results)) 
    return false;
  PROF_STOP_TIMER(GET_GRASPS_SQL);
  // Get the column indices for the columns we care about.
  int pregrasp_joints_column, grasp_joints_column, 
      pregrasp_position_column, grasp_position_column,
      grasp_id_column, epsilon_quality_column, volume_quality_column,
    grasp_contacts_column, grasp_source_name_column, link_param_column, grasp_energy_column;
  PROF_START_TIMER(GET_GRASPS_GETCOLUMN);
  if (!results.GetColumnIndex("grasp_pregrasp_joints", &pregrasp_joints_column) ||
      !results.GetColumnIndex("grasp_grasp_joints", &grasp_joints_column) ||
      !results.GetColumnIndex("grasp_pregrasp_position", &pregrasp_position_column) ||
      !results.GetColumnIndex("grasp_grasp_position", &grasp_position_column) ||
      !results.GetColumnIndex("grasp_id", &grasp_id_column) ||
      !results.GetColumnIndex("grasp_epsilon_quality", &epsilon_quality_column) ||
      !results.GetColumnIndex("grasp_volume_quality", &volume_quality_column) ||
      !results.GetColumnIndex("grasp_energy", &grasp_energy_column) ||
      !results.GetColumnIndex("grasp_contacts", &grasp_contacts_column))
    return false;
	PROF_STOP_TIMER(GET_GRASPS_GETCOLUMN);
  // Turn each database row into a Grasp.
  vector<double> pregrasp_joints, grasp_joints, 
    pregrasp_position, grasp_position, grasp_contacts, params;
  int grasp_id;
  string grasp_source_name;
  std::vector<double> symmetry_axis;
  double epsilon_quality, volume_quality, grasp_energy;
  const int num_rows = results.NumRows();
  grasp_list->reserve(num_rows);
  for (int row = 0; row < num_rows; ++row) {
    grasp_list->push_back(grasp_allocator_->Get());
    Grasp& grasp = *(grasp_list->back());

	pregrasp_joints.clear();
	pregrasp_position.clear();
	grasp_joints.clear();
	grasp_position.clear();

	PROF_START_TIMER(GET_GRASPS_GETFIELD);
    if (!results.GetField(pregrasp_joints_column, row, &pregrasp_joints) || 
        !results.GetField(grasp_joints_column, row, &grasp_joints) || 
        !results.GetField(pregrasp_position_column, row, &pregrasp_position) ||
        !results.GetField(grasp_position_column, row, &grasp_position) || 
        !results.GetField(grasp_id_column, row, &grasp_id) ||
        !results.GetField(epsilon_quality_column, row, &epsilon_quality) ||
        !results.GetField(volume_quality_column, row, &volume_quality) ||
        !results.GetField(grasp_energy_column, row, &grasp_energy) ||
	!results.GetField(grasp_contacts_column, row, &grasp_contacts))
      return false;
	PROF_STOP_TIMER(GET_GRASPS_GETFIELD);
    grasp.SetSourceModel(model);
    grasp.SetHandName(QString::number(hand_id).toStdString());
    grasp.SetEpsilonQuality(epsilon_quality);
    grasp.SetVolumeQuality(volume_quality);
    grasp.SetGraspId(grasp_id);
    grasp.SetEnergy(grasp_energy);

	pregrasp_joints.erase(pregrasp_joints.begin());
	pregrasp_position.erase(pregrasp_position.begin());
	grasp_joints.erase(grasp_joints.begin());
	grasp_position.erase(grasp_position.begin());
    
	grasp.SetGraspParameters(pregrasp_joints, 
                             pregrasp_position, 
                             grasp_joints, 
                             grasp_position);
	grasp.SetContacts(grasp_contacts);
	grasp.SetPregraspJoints(pregrasp_joints);
	grasp.SetPregraspPosition(pregrasp_position);
	grasp.SetFinalgraspJoints(grasp_joints);
	grasp.SetFinalgraspPosition(grasp_position);
	grasp.SetParams(params);
  }
  return true;

  }

bool SqlDatabaseManager::GetGrasps(const Model& model, 
                                   const string& hand_name, 
                                   vector<Grasp*>* grasp_list) const {
  if (grasp_list == NULL) return false;
  Table results;
  PROF_START_TIMER(GET_GRASPS_SQL);
  if (!database_.QueryAndConnect("SELECT * FROM get_grasps('" + model.ModelName() + 
                       "','" + hand_name + "');", &results)) 
    return false;
  PROF_STOP_TIMER(GET_GRASPS_SQL);
  // Get the column indices for the columns we care about.
  int pregrasp_joints_column, grasp_joints_column, 
      pregrasp_position_column, grasp_position_column,
      grasp_id_column, epsilon_quality_column, volume_quality_column,
    grasp_contacts_column, grasp_source_name_column, link_param_column, grasp_energy_column;
  PROF_START_TIMER(GET_GRASPS_GETCOLUMN);
  if (!results.GetColumnIndex("grasp_pregrasp_joints", &pregrasp_joints_column) ||
      !results.GetColumnIndex("grasp_grasp_joints", &grasp_joints_column) ||
      !results.GetColumnIndex("grasp_pregrasp_position", &pregrasp_position_column) ||
      !results.GetColumnIndex("grasp_grasp_position", &grasp_position_column) ||
      !results.GetColumnIndex("grasp_id", &grasp_id_column) ||
      !results.GetColumnIndex("grasp_epsilon_quality", &epsilon_quality_column) ||
      !results.GetColumnIndex("grasp_volume_quality", &volume_quality_column) ||
      !results.GetColumnIndex("grasp_contacts", &grasp_contacts_column) || 
      !results.GetColumnIndex("grasp_source_name", &grasp_source_name_column) || 
      !results.GetColumnIndex("grasp_energy", &grasp_energy_column) || 
      !results.GetColumnIndex("grasp_link_parameters", &link_param_column))
    return false;
	PROF_STOP_TIMER(GET_GRASPS_GETCOLUMN);
  // Turn each database row into a Grasp.
  vector<double> pregrasp_joints, grasp_joints, 
    pregrasp_position, grasp_position, grasp_contacts, params;
  int grasp_id;
  string grasp_source_name;
  std::vector<double> symmetry_axis;
  double epsilon_quality, volume_quality, grasp_energy;
  const int num_rows = results.NumRows();
  grasp_list->reserve(num_rows);
  for (int row = 0; row < num_rows; ++row) {
    grasp_list->push_back(grasp_allocator_->Get());
    Grasp& grasp = *(grasp_list->back());

	pregrasp_joints.clear();
	pregrasp_position.clear();
	grasp_joints.clear();
	grasp_position.clear();

	PROF_START_TIMER(GET_GRASPS_GETFIELD);
    if (!results.GetField(pregrasp_joints_column, row, &pregrasp_joints) || 
        !results.GetField(grasp_joints_column, row, &grasp_joints) || 
        !results.GetField(pregrasp_position_column, row, &pregrasp_position) ||
        !results.GetField(grasp_position_column, row, &grasp_position) || 
        !results.GetField(grasp_id_column, row, &grasp_id) ||
        !results.GetField(epsilon_quality_column, row, &epsilon_quality) ||
        !results.GetField(volume_quality_column, row, &volume_quality) ||
	!results.GetField(grasp_contacts_column, row, &grasp_contacts) ||
	!results.GetField(grasp_source_name_column, row, &grasp_source_name) || 
	!results.GetField(grasp_energy_column, row, &grasp_energy) || 
	!results.GetField(link_param_column, row, &params))
      return false;
    PROF_STOP_TIMER(GET_GRASPS_GETFIELD);
    grasp.SetSourceModel(model);
    grasp.SetHandName(hand_name);
    grasp.SetEpsilonQuality(epsilon_quality);
    grasp.SetVolumeQuality(volume_quality);
    grasp.SetGraspId(grasp_id);

    grasp.SetEnergy(grasp_energy);
    pregrasp_joints.erase(pregrasp_joints.begin());
    pregrasp_position.erase(pregrasp_position.begin());
    grasp_joints.erase(grasp_joints.begin());
    grasp_position.erase(grasp_position.begin());
    
    grasp.SetGraspParameters(pregrasp_joints, 
                             pregrasp_position, 
                             grasp_joints, 
                             grasp_position);
    grasp.SetContacts(grasp_contacts);
    grasp.SetPregraspJoints(pregrasp_joints);
    grasp.SetPregraspPosition(pregrasp_position);
    grasp.SetFinalgraspJoints(grasp_joints);
    grasp.SetFinalgraspPosition(grasp_position);
    grasp.SetSource(grasp_source_name);
    grasp.SetParams(params);    
  }
  return true;
}

bool SqlDatabaseManager::SaveGrasps(const vector<Grasp*> graspList) const {
	Table results;
	for(size_t i = 0; i < graspList.size(); ++i){
		stringstream query_text;                  
		query_text << "SELECT * FROM save_grasp2('" <<
			graspList[i]->SourceModel().ModelName() << "'," <<
			graspList[i]->HandName() << ", '{5, ";

		vector<double> tempArray;
		//pregrasp joints
		tempArray = graspList[i]->GetPregraspJoints();
		size_t j;
		for(j = 0; j < tempArray.size() - 1; ++j){
			query_text << tempArray[j] << ", ";
		}
		query_text << tempArray[j] << "}', ";

		//pregrasp position
		query_text << "'{0, ";
		tempArray = graspList[i]->GetPregraspPosition();
		for(j = 0; j < tempArray.size() - 1; ++j){
			query_text << tempArray[j] << ", ";
		}
		query_text << tempArray[j] << "}', ";

		//finalgrasp joints
		query_text << "'{5, ";
		tempArray = graspList[i]->GetFinalgraspJoints();
		for(j = 0; j < tempArray.size() - 1; ++j){
			query_text << tempArray[j] << ", ";
		}
		query_text << tempArray[j] << "}', ";

		//finalgrasp position
		query_text << "'{0, ";
		tempArray = graspList[i]->GetFinalgraspPosition();
		for(j = 0; j < tempArray.size() - 1; ++j){
			query_text << tempArray[j] << ", ";
		}
		query_text << tempArray[j] << "}', ";

		//contacts
		query_text << "'{";
		tempArray = graspList[i]->GetContacts();
		if (!tempArray.empty()) {
		for(j = 0; j < tempArray.size() - 1; ++j){
			query_text << tempArray[j] << ", ";
		}
		query_text << tempArray[j] << "}', ";
		} else {
			query_text << "}', ";
		}

		//iteration
		tempArray = graspList[i]->GetParams();
		query_text << graspList[i]->Iteration() << ", ";
		

		//energy
		query_text << graspList[i]->Energy() << ", ";

		//epsilon quality
		query_text << graspList[i]->EpsilonQuality() << ", ";

		//volume
		query_text << graspList[i]->VolumeQuality() << ", ";

		//source
		query_text << "'" << graspList[i]->GetSource().c_str() << "')";

		std::cout << query_text.str().c_str();
		
		if (!database_.QueryAndConnect(query_text.str(), &results))
			return false;
	}
	return true;
}
bool SqlDatabaseManager::UpdateGrasp(const std::vector<Grasp*> graspList, FILE * fp) const {
       Table results;
       std::vector<double> tempArray;
       unsigned int j;
       for(size_t i = 0; i < graspList.size(); ++i){
               stringstream query_text;
               query_text << "SELECT * FROM update_grasp(";

               //graspID
               query_text << graspList[i]->GraspId() << ",";

               //finalgrasp joints
               query_text << "'{5, ";
               tempArray = graspList[i]->GetFinalgraspJoints();
               for(j = 0; j < tempArray.size() - 1; ++j){
                       query_text << tempArray[j] << ", ";
               }
               query_text << tempArray[j] << "}', ";

               //finalgrasp position
               query_text << "'{0, ";
               tempArray = graspList[i]->GetFinalgraspPosition();
               for(j = 0; j < tempArray.size() - 1; ++j){
                       query_text << tempArray[j] << ", ";
               }
               query_text << tempArray[j] << "}', ";

               //contacts
               query_text << "'{";
               tempArray = graspList[i]->GetContacts();
               if(tempArray.empty()){
                       query_text << "}', ";
               } else {
                       for(j = 0; j < tempArray.size() - 1; ++j){
                               query_text << tempArray[j] << ", ";
                       }
                       query_text << tempArray[j] << "}', ";
               }
			   //test for NaN
			   if(graspList[i]->EpsilonQuality() != graspList[i]->EpsilonQuality())
				   graspList[i]->SetEpsilonQuality(-1.0);
               //energy
               query_text << -100.0 * graspList[i]->EpsilonQuality() -30.0 *
graspList[i]->VolumeQuality() << ", ";

               //epsilon quality
               query_text << graspList[i]->EpsilonQuality() << ", ";

               //volume
               query_text << graspList[i]->VolumeQuality() << ")";
               //fprintf(fp, "%s ", query_text.str().c_str());
               if (!database_.QueryAndConnect(query_text.str(), &results))
                       return false;
       }

       return true;
}

bool SqlDatabaseManager::SavePCA(const Model & model, const float pca[9]) const{
//output PCA to database
	
	std::stringstream queryText;
	queryText << "Select * From set_model_principal_components('" << model.ModelName() << "', ";
	//create array string
	queryText << "'{";
	//don't output a comma before the last number.
	for(int ind = 0; ind < 8; ++ind){
		queryText << pca[ind] << ',';
	}	queryText << pca[8] <<"}')";
	Table results;
	if(!database_.QueryAndConnect(queryText.str(), &results))
		return false;
	return true;
}

bool SqlDatabaseManager::GetPCA(const Model & model, float pca[9])const{
  Table results;
  stringstream query_text;                  
  query_text << "SELECT get_model_principal_components('" << model.ModelName() << "')";
  if (!database_.QueryAndConnect(query_text.str(), &results)) return false;
  vector<float> pca_vector;
  pca_vector.reserve(9);
  if (results.NumColumns() == 0 || results.NumRows() == 0) return false;
  if (!results.GetField(0, 0, &pca_vector)) return false;
  for (int i = 0; i < 9; ++i) pca[i] = pca_vector[i];
  return true;
}

  Grasp* SqlDatabaseManager::GetGrasp(const int graspIdNumber){
    //get a single grasp by its grasp ID number and all of the data necessary to load the associated model
  Table results;
  int pregrasp_joints_column, grasp_joints_column, pregrasp_position_column, grasp_position_column, grasp_id_column,
    epsilon_quality_column, volume_quality_column, grasp_contacts_column, grasp_source_name_column, scaled_model_name_column, 
    hand_name_column, link_param_column;

  if (!database_.QueryAndConnect("SELECT * FROM get_grasp_by_id(" + QString::number(graspIdNumber).toStdString() +")", &results)) 
    return false;

  Grasp * grasp(NULL);
 if (!results.GetColumnIndex("grasp_pregrasp_joints", &pregrasp_joints_column) ||
      !results.GetColumnIndex("grasp_grasp_joints", &grasp_joints_column) ||
      !results.GetColumnIndex("grasp_pregrasp_position", 
                              &pregrasp_position_column) ||
      !results.GetColumnIndex("grasp_grasp_position", &grasp_position_column) ||
      !results.GetColumnIndex("grasp_id", &grasp_id_column) ||
      !results.GetColumnIndex("grasp_epsilon_quality", &epsilon_quality_column) ||
      !results.GetColumnIndex("grasp_volume_quality", &volume_quality_column) ||
	  !results.GetColumnIndex("grasp_contacts", &grasp_contacts_column) ||
	  !results.GetColumnIndex("scaled_model_name", &scaled_model_name_column) ||
	  !results.GetColumnIndex("hand_name", &hand_name_column) ||
	  !results.GetColumnIndex("grasp_source_name", &grasp_source_name_column) ||
     !results.GetColumnIndex("grasp_link_parameters", &link_param_column))
    return grasp;

  // Turn each database row into a Grasp.
  vector<double> pregrasp_joints, grasp_joints, 
    pregrasp_position, grasp_position, grasp_contacts, params;
  int grasp_id;
  string grasp_source_name, hand_name, scaled_model_name;
  double epsilon_quality, volume_quality;

  pregrasp_joints.clear();
  pregrasp_position.clear();
  grasp_joints.clear();
  grasp_position.clear();
  
  PROF_START_TIMER(GET_GRASPS_GETFIELD);
    if (!results.GetField(pregrasp_joints_column, 0, &pregrasp_joints) || 
        !results.GetField(grasp_joints_column, 0, &grasp_joints) || 
        !results.GetField(pregrasp_position_column, 0, &pregrasp_position) ||
        !results.GetField(grasp_position_column, 0, &grasp_position) || 
        !results.GetField(grasp_id_column, 0, &grasp_id) ||
        !results.GetField(epsilon_quality_column, 0, &epsilon_quality) ||
        !results.GetField(volume_quality_column, 0, &volume_quality) ||
	!results.GetField(grasp_contacts_column, 0, &grasp_contacts) ||
	!results.GetField(hand_name_column, 0, &grasp_contacts) ||
	!results.GetField(grasp_contacts_column, 0, &grasp_contacts) ||
	!results.GetField(grasp_source_name_column, 0, &grasp_source_name) || 
        !results.GetField(link_param_column, 0, &params))
      return false;

    //load the associated model -- does not import an geometry!
    LoadModelFunctor load_model_functor(results, model_root_);
    Model *model = model_allocator_->Get();
    if (!load_model_functor(model, 0)) {
      //std::cout << "load model failed\n";
      return grasp;
    }
    //create the grasp
    grasp = grasp_allocator_->Get();
    grasp->SetSourceModel(*model);
    grasp->SetHandName(hand_name);
    grasp->SetEpsilonQuality(epsilon_quality);
    grasp->SetVolumeQuality(volume_quality);
    grasp->SetGraspId(grasp_id);
    
    pregrasp_joints.erase(pregrasp_joints.begin());
    pregrasp_position.erase(pregrasp_position.begin());
    grasp_joints.erase(grasp_joints.begin());
    grasp_position.erase(grasp_position.begin());
    
    grasp->SetGraspParameters(pregrasp_joints, 
                             pregrasp_position, 
                             grasp_joints, 
                             grasp_position);
    grasp->SetContacts(grasp_contacts);
    grasp->SetPregraspJoints(pregrasp_joints);
    grasp->SetPregraspPosition(pregrasp_position);
    grasp->SetFinalgraspJoints(grasp_joints);
    grasp->SetFinalgraspPosition(grasp_position);
    grasp->SetSource(grasp_source_name);
    grasp->SetParams(params);
    return grasp;
    
    
  }

  EigenHandLoader * SqlDatabaseManager::getEigenhand(unsigned int eigenhandNumber) const
  {
    std::stringstream query_text;
    Table results;
    std::vector<unsigned int> fingerIDList;
    std::vector<double> palmScale;
    int palm_scale_column, finger_id_column, finger_base_positions_column, generation_column;

    //construct query text
    query_text << "SELECT * from hand where hand_id = " << eigenhandNumber;
    
    //query database
    if (!database_.QueryAndConnect(query_text.str(), &results)) return NULL;

    //Check that query succeeded
    if (results.NumColumns() == 0 || results.NumRows() == 0) return NULL;

    //Get columns from hand table
    if(!results.GetColumnIndex("palm_scale", &palm_scale_column) || 
       !results.GetColumnIndex("finger_id_list", &finger_id_column) || 
       !results.GetColumnIndex("finger_base_positions", &finger_base_positions_column) || 
       !results.GetColumnIndex("generation", &generation_column)) return NULL;
    
    //Create hand descriptor
    HandDescription hd;
    hd.handID = eigenhandNumber;

    //Get parameters
    if (!results.GetField(palm_scale_column, 0, &hd.palmScale)) return NULL;
    if (!results.GetField(finger_id_column, 0, &hd.fingerIDList)) return NULL;
    if (!results.GetField(finger_base_positions_column, 0, &hd.fingerBasePositions)) return NULL;
    if (!results.GetField(generation_column, 0, &hd.generation)) return NULL;

    if(hd.fingerBasePositions.size() != hd.fingerIDList.size()) return NULL;

    EigenHandLoader * ehl = new EigenHandLoader();
    ehl->hd = new HandDescription(hd);
        
    
    for(unsigned int fIterator = 0; fIterator < hd.fingerIDList.size(); ++fIterator)
      {
	Table fResults;
	int finger_id_column, link_list_column, joint_range_list_column;

	//clear query string
	query_text.str("");
	query_text.clear();

	
	query_text << "Select * from finger where finger_id = " << hd.fingerIDList[fIterator];

	//query database
	if (!database_.QueryAndConnect(query_text.str(), &fResults)) break;
	
	//Check that query succeeded
	if (fResults.NumColumns() == 0 || fResults.NumRows() == 0) break;
	
	//Get columns from hand table
	if(!fResults.GetColumnIndex("link_length_list", &link_list_column) ||
	   !fResults.GetColumnIndex("joint_range_list", &joint_range_list_column)
	   ) break;
	
	//Create finger descriptor
	FingerDescription fd;

	fd.fingerID = hd.fingerIDList[fIterator];

	if (!fResults.GetField(link_list_column, 0, &fd.jointLenList) || 
	    !fResults.GetField(joint_range_list_column, 0, &fd.jointRangeList))
	  break;
	
	if (fd.jointLenList.size() != fd.jointRangeList.size()/2.0) break;
	ehl->fdList.push_back(new FingerDescription(fd));
      }


    if (ehl->fdList.size() != hd.fingerIDList.size())
      {
	delete ehl;
	ehl = NULL;
      }

    return ehl;
  }
 




  //! Returns a list of hand names with the structure HandName_handID
bool SqlDatabaseManager::HandList(std::vector<string> & handNameList) const {
  std::string query_text = "Select hand_name,hand_id from hand;";
  Table results;
  int handIDColumn, handNameColumn, handID;
  string handName;

  if (!database_.QueryAndConnect(query_text, &results)) return false;

  //Get Columns from table
  if(!results.GetColumnIndex("hand_id", &handIDColumn) ||
     !results.GetColumnIndex("hand_name", &handNameColumn) )
    return false;
  
  for (unsigned int row = 0; row < results.NumRows(); ++row)
    {
      std::stringstream ss;
      results.GetField(handIDColumn, row, &handID);
      results.GetField(handNameColumn, row, & handName);
      ss << handName << "_" << handID;      
      handNameList.push_back(string(ss.str()));
      
    }
  return true;

}
}  // end namespace db_planner
