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
// Author(s):  Hao Dang and Matei T. Ciocarlie
//
// $Id: grasp.h,v 1.16 2009/10/08 16:13:11 cmatei Exp $
//
//######################################################################

/*! \file 
  \brief Defines the %Grasp and &GraspAllocator classes.
 */


#ifndef DB_PLANNER_GRASP_H
#define DB_PLANNER_GRASP_H

#include <string>
#include <vector>
#include "model.h"
using std::string;
using std::vector;
class Hand;

namespace db_planner {

class Grasp {
 private: 
  //! The model being grasped
  const Model* source_model_;
  //! The id of the grasp from the database.
  int grasp_id_;
  //! The iteration of the planner during which this grasp was run
  int iteration_;
  //! The source of this grasp: EGPlanner, human operator, etc.
  string source_;
  //! The name of the hand the grasp is for.
  string hand_name_;
  //! Ferrari-Canny quality measures.
  double epsilon_quality_, volume_quality_;
  //! Quality value as used by automated grasp planners
  double energy_;
  //! The actual parameters of the grasp.
  vector<double> pregrasp_joints_, final_grasp_joints_, pregrasp_position_, final_grasp_position_, contacts_;

  //! Stores parameters used to specify hand
  std::vector<double> params_;


 public:
  virtual ~Grasp(){}
  void SetSourceModel(const Model& source_model) { 
    source_model_ = &source_model; 
  }
  void SetHandName(const string& hand_name) { hand_name_ = hand_name; }
  void SetPregraspJoints(const vector<double>& pregraspJoints) { pregrasp_joints_ = pregraspJoints; }
  void SetPregraspPosition(const vector<double>& pregraspPosition) { pregrasp_position_ = pregraspPosition; }
  void SetFinalgraspJoints(const vector<double>& finalgraspJoints) { final_grasp_joints_ = finalgraspJoints; }
  void SetFinalgraspPosition(const vector<double>& finalgraspPosition) { final_grasp_position_ = finalgraspPosition; }
  void SetContacts(const vector<double>& contacts) { contacts_ = contacts; }
  void SetParams(const vector<double>& params) { params_ = params; }
  void SetIteration(const int iteration){iteration_ = iteration;}

  vector<double> GetPregraspJoints() const { return pregrasp_joints_; }
  vector<double> GetPregraspPosition() const { return pregrasp_position_; }
  vector<double> GetFinalgraspJoints() const { return final_grasp_joints_; }
  vector<double> GetFinalgraspPosition() const { return final_grasp_position_; }
  vector<double> GetContacts() const { return contacts_; }
  vector<double> GetParams() const { return params_; }


  string getHandName(){return hand_name_;}

  void SetEpsilonQuality(const double epsilon_quality) {
    epsilon_quality_ = epsilon_quality;
  }
  void SetVolumeQuality(const double volume_quality) {
    volume_quality_ = volume_quality;
  }
  void SetEnergy(const double energy) {
    energy_ = energy;
  }
  void SetGraspId(const int grasp_id) { grasp_id_ = grasp_id; }
  void SetSource(string source){source_ = source;}
  string GetSource() const {return source_;}
  const Model& SourceModel() const { return *source_model_; }
  const string& HandName() const { return hand_name_; }
  double EpsilonQuality() const { return epsilon_quality_; }
  double VolumeQuality() const { return volume_quality_; }
  double Energy() const {return energy_;}
  int GraspId() const { return grasp_id_; }
  int Iteration() const {return iteration_;}
  //! Transform a grasp by some 4x4 transform.
  /*! Transforms are left-multiply and column major.
      This base implementation always fails. */
  virtual bool Transform(const float /*transform*/[16]) { return false; }
  virtual bool SetGraspParameters(const vector<double>& /*pregrasp_joints*/, 
                                  const vector<double>& /*pregrasp_position*/, 
                                  const vector<double>& /*grasp_joints*/,
                                  const vector<double>& /*grasp_poisition*/) {
    return false;
  }

                      
};

//! A class to allocate a new Grasp object, which may be a derived type.
class GraspAllocator {
public:
	virtual Grasp* Get() const = 0;
	virtual bool setHand(Hand * h) = 0;
};

}
// end namespace db_planner

#endif  // DB_PLANNER_GRASP_H
