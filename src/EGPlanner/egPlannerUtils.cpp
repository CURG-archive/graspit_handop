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
// Author(s):  Jonathan Weisz
//
//######################################################################

#include "egPlannerUtils.h"
#include "egPlanner.h"
#include "searchState.h"
#include "searchEnergy.h"
#include "robot.h"
#include "body.h"
#include "matvec3D.h"
#include "grasp.h"
#include "graspit_db_grasp.h"
#include "debug.h"
#include "guidedPlanner.h"
#include "DBase/DBPlanner/db_manager.h"
#include "exitReturnCodes.h"

namespace egPlannerUtils
{
  /*! Creates a grasp planning state for the EigenGrasp planner
   * which aligns the Y axis of the hand with the Y axis of the target
   * object and fixes it so that the planner is forced
   * to keep the Y axes parallel. This is useful
   * for planning against the CGDB because most objects
   * have their 1st principle component aligned to the Y
   * axis.
   */
  GraspPlanningState *gpsWithYParallelToCurrentY(Hand * h, 
						 const Body * const refBody)	
  {
    //Create new object state
    GraspPlanningState * handObjectState = new GraspPlanningState(h); 
    handObjectState->setPositionType(SPACE_COMPLETE);
    
    //Align hand and object Y axes
    handObjectState->getPosition()->setTran(h->getTran()*refBody->getTran().inverse());
    
    //fix x and z, leave y and w free.
    handObjectState->getVariable(6)->setFixed(false);
    handObjectState->getVariable(8)->setFixed(true);
    handObjectState->getVariable(5)->setFixed(false);
    handObjectState->getVariable(7)->setFixed(true);
    
    return handObjectState;
  }


  /*!
   * Aligns the hand so that the vector \handVector in the hand's coordinate
   * system aligns to some other vector in the world's coordinate system
   * and then moves out of collision. 
   */
  
  bool alignHandYToV(Hand * h, vec3 & handVector, const vec3 & targetVector){
    transf t;	
    transf targetHandTrans = transf(transV1OnToV2(vec3(1,0,0),targetVector),h->getTran().translation());
    h->setTran(targetHandTrans);
    h->findInitialContact(0);
    return true;
  }
  
  /*! Convenience function to find the quaternion that
   * represents the rotation between to vectors
   */
  Quaternion transV1OnToV2(const vec3 &v1, const vec3 &v2){
    return Quaternion(acos(v1%v2), v1*v2/*rotate around common normal*/);
  }

  /*! The guided planner produces grasps in a "pregrasping" pose
   *  that are not contact with the object. In order to get all of the
   *  information necessary to save the grasp, such as the final contact locations
   *  we must refine this grasp to a final grasp before saving it in the database.
   *  Currently this function uses a fixed energy type to refine the grasp,
   *  but this may change in the future.
   */
  GraspitDBGrasp* synthesize(GraspPlanningState* pre, GraspPlanningState* fin, SearchEnergy * se = NULL)
  {

    //synthesize a new graspit_db_grasp
    // store it into CGDB
    GraspitDBGrasp* gp;
    
    gp = new GraspitDBGrasp(pre->getHand());
          
    gp->SetHandName(pre->getHand()->getName().toStdString());
    db_planner::Model* m = pre->getHand()->getGrasp()->getObject()->getDBModel();
    gp->SetSourceModel(*m);
  
    //the pre-grasp's position is not in eigengrasp space, so we must save it in DOF space
    //these are only used for the representation of pregrasp in final grasp's format
    //convert it's tranform to the Quaternion__Translation format
    //make sure you pass it sticky=true, otherwise information is lost in the conversion
    pre->setPositionType(SPACE_COMPLETE,true);
    
    //we will want to save exact DOF positions, not eigengrasp values
    //again, make sure sticky=true
    pre->setPostureType(POSE_DOF,true);
    gp->setPreGraspPlanningState(new GraspPlanningState(pre));
    
    //start analyzing and generate the final grasp
    
    bool legal = 0;
    double energy = -1;
    se->analyzeState(legal,energy,fin,false);
    //se->setHandAndObject(pre->getHand(),pre->getObject());
    //pre->execute();
    //save the qualities -- in case fin is not the right kind of state, 
    //make it the right kind
    fin->setPositionType(SPACE_COMPLETE,true);
    fin->setPostureType(POSE_DOF,true);
    fin->saveCurrentHandState();
    fin->setEpsilonQuality(se->getEpsQual());
    fin->setVolume(se->getVolQual());    
    
    //Contacts is not copied in copy constructor
    GraspPlanningState * fin_tmp = new GraspPlanningState(fin);

    //the contacts
    std::vector<double> tempArray;
    tempArray.clear();
    for(int i = 0; i < fin->getHand()->getGrasp()->getNumContacts(); ++ i)
      {
    Contact * c = fin->getHand()->getGrasp()->getContact(i);
    fin_tmp->getContacts()->push_back(c->getPosition());
    }
    
    gp->setFinalGraspPlanningState(fin_tmp);
    if(fin->getEpsilonQuality() > 0.01)
      gp->SetEnergy(pre->getEnergy());
    else
      gp->SetEnergy(1e10);
    delete fin_tmp;
    return gp;
  }

  /*! Takes grasps found by a GuidedPlanner type EGPlanner
   *  and saves them to the database. To do this, the pregrasp 
   *  position must be refined to a final grasp so that we can
   *  robustly find the contacts and final energy. 
   *  Pregrasps occur as every other grasp in the grasp list.
   */
  bool GuidedPlannerSaver::saveGraspList( EGPlanner * finishedPlanner, db_planner::TaskRecord * rec){
  // set default return value - any failure will short circuit the rest of the loop
  // and exit with false.
  bool retVal = true;	
	
  // for storing it into CGDB
  std::vector<db_planner::Grasp*> gpList;
  
  for(int i = 0; i < finishedPlanner->getListSize() - 1; i+=2){
    DBGA("Synthesizing grasp: " << i);
    gpList.push_back(synthesize(const_cast<GraspPlanningState*>(finishedPlanner->getGrasp(i)), const_cast<GraspPlanningState*>(finishedPlanner->getGrasp(i+1))));
    gpList.back()->SetSource("EIGENGRASPS_TASK_1");
    gpList.back()->SetIteration(mGeneration);
  }

  DBGA("Saving grasps - grasp number: " << gpList.size());
  if(!mDBMgr.SaveGrasps(gpList)){
    DBGA("Failed to Save Grasps");
    retVal = false;
  }
  for(int i = 0; i < finishedPlanner->getListSize()/2; ++i){
    delete gpList[i];
  }
  gpList.clear();
  return retVal;
}

/*! Creates a simulated annealing EGPlanner with reasonable
 *  default parameters.
 */
 EGPlanner * SimAnPlannerFactory::newPlanner(Hand * mHand, 
							  GraspitDBModel * m){
   EGPlanner * mPlanner = new SimAnnPlanner(mHand);	
   GraspPlanningState * ns = new GraspPlanningState(mHand);
   
   ns->setPositionType(SPACE_COMPLETE);
   ns->setObject(mHand->getWorld()->getGB(0));
   ns->setRefTran(mHand->getWorld()->getGB(0)->getTran());
   ns->reset();
   
   ns->saveCurrentHandState();
   static_cast<SimAnnPlanner *>(mPlanner)->setModelState(ns);
   mPlanner->setEnergyType(ENERGY_CONTACT);
   mPlanner->setContactType(CONTACT_PRESET);
   mPlanner->setMaxSteps(60000);
   mPlanner->setRepeat(false);  
   mPlanner->invalidateReset();
   mPlanner->resetPlanner();
   return mPlanner;
 }


 /*!
  * Creates a guided planner factory with reasonable default parameters
  */
 EGPlanner * GuidedPlannerFactory::newPlanner(Hand * mHand, 
					      GraspitDBModel * m){
   EGPlanner * mPlanner = new GuidedPlanner(mHand);	
   GraspPlanningState * ns = new GraspPlanningState(mHand);
   // Back off the object a little. This produces more reasonable results as otherwise
   // many of the early jumps produce states that intersect the object
   mHand->setTran(translate_transf(vec3(0,0,100)));
   ns->setPositionType(SPACE_COMPLETE);
   ns->setObject(mHand->getWorld()->getGB(0));
   ns->setRefTran(mHand->getWorld()->getGB(0)->getTran());
   ns->reset();
   ns->saveCurrentHandState();
   
   static_cast<SimAnnPlanner *>(mPlanner)->setModelState(ns);
   mPlanner->setContactType(CONTACT_PRESET);
   mPlanner->setMaxSteps(500000);
   mPlanner->setRepeat(false);  
   mPlanner->invalidateReset();
   return mPlanner;
 };

 /*!
  * Saves a list of grasp planning states from an EGPlanner to the database
  */
  bool SimAnPlannerSaver::saveGraspList(EGPlanner * finishedPlanner, db_planner::TaskRecord * rec)
 {
   DBGA("Saving" << finishedPlanner->getListSize() << "Grasps "  );
   bool retVal = true;	
   // for storing it into CGDB
   std::vector<db_planner::Grasp*> gpList;
   SearchEnergy se;
   se.setType(ENERGY_GFO);
   bool legal;
   double energy;
   for(int i = 0; i < finishedPlanner->getListSize(); i+=1){
     //se.analyzeState(legal, energy, finishedPlanner->getGrasp(i), false);
     GraspPlanningState final(finishedPlanner->getGrasp(i));
     DBGA("Synthesizing grasp: " << i);
     gpList.push_back(synthesize(const_cast<GraspPlanningState*>(finishedPlanner->getGrasp(i)), &final, &se));
     gpList.back()->SetIteration(mGeneration);
     std::vector<double> params;
     params.push_back(finishedPlanner->getGrasp(i)->getAttribute("PlanningTime"));
     params.push_back(finishedPlanner->getGrasp(i)->getAttribute("PlanningSteps"));
     gpList.back()->SetParams(params);
     //gpList.back()->SetSource(mSource.toStdString());
     //gpList.back()->SetEnergy(finishedPlanner->getGrasp(i)->getEnergy());
     mDBMgr.SetTaskStatus(*rec,"RUNNING");
   }
   DBGA("Grasp list generated");
  
   db_planner::TaskRecord test;
   mDBMgr.GetTaskStatus(*rec,test);
   if (!test.taskOutcomeName.compare("DONE")){
     std::cout << "Some other instance finished running; Exiting";
     exit(JOB_ALREADY_COMPLETED);
   }

   if(!mDBMgr.SaveGrasps(gpList)){
     DBGA("Failed to Save Grasps");
     retVal = false;
   }
   for(int i = 0; i < gpList.size(); ++i){
     //delete gpList[i];
   }
   gpList.clear();
   return retVal;
 }

};
