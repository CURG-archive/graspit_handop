//######################################################################
//
// GraspIt!
// Copyright (C) 2002-2012  Columbia University in the City of New York.
// All rights reserved.
//
// This software is protected under a Research and Educational Use
// Only license, (found in the file LICENSE.txt), that you should have
// received with this distribution.
//
// Author(s):  Jonathan Weisz
//
//
//######################################################################

#ifndef _GENERICGRASPPLANNINGTASK_H_
#define _GENERICGRASPPLANNINGTASK_H_
#include "graspPlanningTask.h"
#include "eigenhand_db_interface.h"

/*! 
  Grasp planning task with factory for creating planner for added flexibility
  The thing the factory creates must know how to destroy itself completely

*/
template <class EGPlannerFactory, class GraspSaver>
class GenericGraspPlanningTask:public GraspPlanningTask{

 protected:
  EGPlannerFactory & mPlannerFactory; //! Function that encapsulates creating a new planner.

  GraspSaver saver;

  bool saveGrasps(){return saver.saveGraspList(mPlanner);}; //! Save the grasps from the current planner

  //!Load the existing object
  /*!
    Load the target object -- If this is a regular object file, just load it, otherwise assume that it's a world
    and load the entire world.
  */
  virtual void getObject()
  {
    //Test if this is a world file - this is not the most robust test. 
    if(mRecord.misc.find(".xml") == std::string::npos){
      GraspPlanningTask::getObject();
      return;
    }
    
    World * w = mHand->getWorld();
    //load world
    if (w->load(QString((string(getenv("GRASPIT")) + mRecord.misc).c_str())) != SUCCESS)
      {
	DBGA("harvardHandPlanningTask:: Failed to load world: " << mRecord.misc <<"\n");
	mStatus=ERROR;
	return;
      }
    if (w->getNumGB() != 1)
      {
	DBGA("harvardHandPlanningTask:: Graspable body number = : " << w->getNumGB() <<"  Fatal Error \n");
	mStatus=ERROR;
	return;
      }
    mHand->findInitialContact(1000);
    //set mObject
    mObject = w->getGB(0);
    mObject->setMaterial(wood);
    
    //back the hand off the object if it is overlapped.
    //mHand->findInitialContact(10);
    mObject->setDBModel(static_cast<GraspitDBModel *>(mRecord.model));
    
    //disable collisions between obstacles and main object
    for(int bi = 0; bi < w->getNumBodies(); bi ++){
      Body * btest = w->getBody(bi);
      if (btest == mObject)
	continue;
      if(dynamic_cast<Link *>(btest) || dynamic_cast<GraspableBody *>(btest))
	continue;
      w->toggleCollisions(false, btest, mObject);
    }     
  };

public:
  //! Constructor
  GenericGraspPlanningTask(TaskDispatcher *disp, db_planner::DatabaseManager *mgr, 
			   db_planner::TaskRecord rec, EGPlannerFactory * egplannerFactory, int taskID, QString taskName) 
    : GraspPlanningTask(disp, mgr, rec), 
    mPlannerFactory(*egplannerFactory), 
    saver(mgr,taskID, taskName){};	

  //! Start the planning task
  /*!
    Loads the hand and object, generates a new planner, and starts the planning process. 
   */
  virtual void start(){
    //sets mHand
    getHand();    
    if(!mHand)
      return;
    saver.setGeneration(eh->hd->generation.back());
    //sets mObject
    getObject();	
    //get a planner from the factory
    mHand->findInitialContact(0);
    //create new planner
    mPlanner = mPlannerFactory.newPlanner(mHand, static_cast<GraspitDBModel*>(mRecord.model));

    //if this task is being run without rendering, disable rendering of the objects.
    if(graspItGUI->useConsole()){
      mHand->setRenderGeometry(false);
      mObject->setRenderGeometry(false);
		  mPlanner->setRenderType(RENDER_NEVER);
    }
    else
      mPlanner->setRenderType(RENDER_LEGAL);


    //max time set from database record
    if (mRecord.taskTime >= 0){
      mPlanner->setMaxTime(mRecord.taskTime);      
    } else {
      mPlanner->setMaxTime(-1);
    }
    
    //start running the planner
    startPlanner();
  };
  

  //! Handle completion of the task
  /*!
    When the task is finished, stop running the planner, save the grasps, and return.
   */
  virtual void plannerComplete(){
    // if task is still running, continue. 
    if (mStatus != RUNNING) return;

    // otherwise, save the existing grasps.
    if(!saveGrasps()) {
      //if saving the grasps fails, set the task to failed.
      //mStatus = ERROR; 
      //stop the planner
      mPlanner->stopPlanner();
      //and quit
      return;
    }
    //everything went ok, mark everything as finished, and return. 
    mStatus = DONE;
    return;
  };

};



//! A class that generates new tasks that can plan and save a grasp.
/*!
  This is a convenience class for bringing together a grasp planning task and a class
  that knows how to save grasps for that planner.
 */
template <class EGPlannerFactory, class Saver>
  class GenericGraspPlanningTaskFactory:public TaskFactory{

 protected:
  EGPlannerFactory mEGPlannerFactory;
  int mTaskDescriptorNumber;
  QString mTaskDescriptorName;

 public:
 GenericGraspPlanningTaskFactory(db_planner::DatabaseManager * db, 
				 int taskDescriptorNumber, 
				 QString taskDescriptorName) 
   : mEGPlannerFactory(db),
    mTaskDescriptorNumber(taskDescriptorNumber),
    mTaskDescriptorName(taskDescriptorName){};
  
  //!Generate a new task.
  virtual Task* getTask(TaskDispatcher *disp, db_planner::DatabaseManager *mgr, 
			db_planner::TaskRecord rec){
    // if the task type is not one which this Planner can handle, return null
    if (rec.taskType != mTaskDescriptorNumber)
      return NULL;
    return new GenericGraspPlanningTask<EGPlannerFactory, Saver>(disp, mgr, rec, 
								 &mEGPlannerFactory, 
								 mTaskDescriptorNumber,
								 mTaskDescriptorName);
  };
};


#endif
