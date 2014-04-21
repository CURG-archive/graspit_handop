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
// Author(s):  Matei T. Ciocarlie
//
// $Id: graspPlanningTask.cpp,v 1.1 2009/10/08 16:13:11 cmatei Exp $
//
//######################################################################

#include "graspPlanningTask.h"

#include <QString>

#include "mytools.h"
#include "graspitGUI.h"
#include "ivmgr.h"
#include "world.h"
#include "robot.h"
#include "body.h"
#include "searchState.h"
#include "loopPlanner.h"

#include "DBPlanner/sql_database_manager.h"
#include "eigenhand_db_interface.h"
#include "graspit_db_grasp.h"
#include "graspit_db_model.h"
#include "grasp.h"
#include "exitReturnCodes.h"
#include "debug.h"


GraspPlanningTask::GraspPlanningTask(TaskDispatcher *disp, 
				     db_planner::DatabaseManager *mgr, 
				     db_planner::TaskRecord rec) : Task(disp, mgr, rec), mObject(NULL), mHand(NULL), mPlanner(NULL)
{
	//nothing so far
}


/*! 
  Destructor 
  Remove objects any added objects from the collision system.
 */
GraspPlanningTask::~GraspPlanningTask()
{
  
  //remove the planning object from the world, but do not delete it
  if (mObject)
    mObject->getWorld()->destroyElement(mObject, false);
  //clean up the loaded geometry
  //the model itself is left around. we don't have a good solution for that yet
  if(mRecord.model)
    static_cast<GraspitDBModel*>(mRecord.model)->unload();
  if (mPlanner)
    delete mPlanner;
}



//! Read the scaling parameters from the task parameteres and scale each link of the hand
/*void scaleHand(Hand * h, db_planner::TaskRecord &  record){
  std::vector<mat3> scales;
  getDiagonalMatrices(scales, record.params);
  if (scales.size() > 0)
    RobotTools::scaleHand(scales, h);
}
*/
/*!
  If the hand is not yet loaded, load the hand and make sure that there is a set of virtual contacts for the hand.
 */
void GraspPlanningTask::getHand(){
  World *world = graspItGUI->getIVmgr()->getWorld();
  mHand = NULL;
  //check if the currently selected hand is the same as the one we need
  //if not, load the hand we need
  if (world->getCurrentHand() && 
	    GraspitDBGrasp::getHandDBName(world->getCurrentHand()) == QString(mRecord.handName.c_str())) {
    DBGA("Grasp Planning Task: using currently loaded hand");
    mHand = world->getCurrentHand();
  } else {    
    //Get the hand from the database name stored in the task.
    //mHand = GraspitDBGrasp::loadHandFromDBName(QString(mRecord.handName.c_str()));
    //If that didn't work, try the eigenhand loader
    if ( !mHand )
      {	
	eh = mDBMgr->getEigenhand(mRecord.handId);
	if (eh){
	  mHand = eh->loadHand(world);
	  if (mHand){
	    transf t = translate_transf(vec3(0,-1000,0));	  
	    mHand->setTran(t);
	  }
	}
      }

    if ( !mHand || !mDBMgr->setHand(mHand)) {
      DBGA("Failed to load hand");
      mDBMgr->SetTaskStatus(mRecord, "ERROR",true);
      exit(FAILED_TO_LOAD_HAND);
      mStatus = ERROR;
      return;
    }
    if(mRecord.params.size() >= 6)
      mHand->getGrasp()->setTaskWrench(&mRecord.params[0]);
  }
  if (mRecord.params.size() < 9){
    mRecord.params.push_back(0);
    mRecord.params.push_back(0);
    mRecord.params.push_back(0);
  }

  //check for virtual contacts
  if (mHand->getNumVirtualContacts()==0) {    
    DBGA("Specified hand does not have virtual contacts defined");
    exit(FAILED_TO_LOAD_VIRTUAL_CONTACTS);
    mStatus = ERROR;
    return;
  }
  
  //scale the links of the hand if necessary.
  //scaleHand(mHand, mRecord);
}


/*!
  Start the planner
  
  Connects the signals needed to monitor the progress of the planner.
  Then start the planner running.
 */
void GraspPlanningTask::startPlanner(){
  QObject::connect(mPlanner, SIGNAL(complete()), this, SLOT(plannerComplete()));
  QObject::connect(mPlanner, SIGNAL(loopUpdate()), this, SLOT(plannerLoopUpdate()));
  QObject::connect(mPlanner, SIGNAL(update()), this, SLOT(plannerUpdated()));
  
  if (!mPlanner->resetPlanner()) {
    DBGA("Grasp Planning Task: failed to reset planner");
    mStatus = ERROR;
    return ;
  }
  
  //load all already known grasps so that we avoid them in current searches
  //	mLastSolution = mPlanner->getListSize();
  
  DBGA("Planner started");
  
  mPlanner->startPlanner();
  mStatus = RUNNING;
}


/*!
  Load the object from the task record.

 */
void GraspPlanningTask::getObject(){

  //load the model
  GraspitDBModel *model = static_cast<GraspitDBModel*>(mRecord.model);
  if (model->load(graspItGUI->getIVmgr()->getWorld()) != SUCCESS) {
    //attempt repair
    DBGA("Grasp Planning Task: failed to load model");
    mStatus = ERROR;
    exit(FAILED_TO_LOAD_OBJECT);
    return;
  }
  
  //Get the object from the model
  mObject = model->getGraspableBody();
  mObject->addToIvc();
  //Add the body to the world
  graspItGUI->getIVmgr()->getWorld()->addBody(mObject);
  mObject->setMaterial(wood);
  
  //Uncomment to add table obstacle to the world
  //	Body * table = graspItGUI->getIVmgr()->getWorld()->importBody("Body", QString(getenv("GRASPIT"))+ QString("/models/obstacles/zeroplane.xml"));
  //	graspItGUI->getIVmgr()->getWorld()->addBody(table);
  return;
}



/*!
  Start running the task

  First gets the hand and object, then creates a starting position for the planner
  Then it generates a loop planner and begins planning. 
 */
void GraspPlanningTask::start()
{
  //sets mHand
  getHand();
  if(!mHand)
    {
      DBGA("Failed to start planner");
    return;
    }
  //sets mObject
  getObject();
  //initialize the planner
  GraspPlanningState seed(mHand);
  seed.setObject(mObject);
  seed.setPositionType(SPACE_AXIS_ANGLE);
  seed.setPostureType(POSE_EIGEN);
  seed.setRefTran(mObject->getTran());
  seed.reset();
  
  mPlanner = new LoopPlanner(mHand);	
  mPlanner->setEnergyType(ENERGY_STRICT_AUTOGRASP);
  mPlanner->setContactType(CONTACT_PRESET);
  //	mPlanner->setMaxSteps(65000);
  mPlanner->setRepeat(true);
  //max time set from database record
  if (mRecord.taskTime >= 0){
    mPlanner->setMaxTime(mRecord.taskTime);
	} else {
    mPlanner->setMaxTime(-1);
  }
  static_cast<SimAnnPlanner*>(mPlanner)->setModelState(&seed);
  startPlanner();
}


/*!
  Responds to the completion of the planner.
  Attempts to save the grasp and notes whether or not saving the state succeeds or fails.
 */

void GraspPlanningTask::plannerComplete()
{
  DBGA("planner Complete");
  //save solutions that have accumulated in last loop
  //plannerLoopUpdate();
  if(!saveGrasps())
    mStatus = ERROR;
  else	//finish
    mStatus = DONE;
}


/*!
  Responds to the updates of the planner by attempting to save the 
  most recently found grasps.
 */
void GraspPlanningTask::plannerLoopUpdate()
{
  if (mStatus != RUNNING) return;
  //save all new solutions to database
  for(int i=mLastSolution; i<mPlanner->getListSize(); i++) {
    //copy the solution so we can change it
    GraspPlanningState *sol = new GraspPlanningState(mPlanner->getGrasp(i));

    //convert it's tranform to the Quaternion__Translation format
    //make sure you pass it sticky=true, otherwise information is lost in the conversion
    sol->setPositionType(SPACE_COMPLETE,true);

    //we will want to save exact DOF positions, not eigengrasp values
    //again, make sure sticky=true
    sol->setPostureType(POSE_DOF,true);

    //we are ready to save it
    if (!saveGrasp(sol)) {
      DBGA("GraspPlanningState: failed to save solution to dbase");
      mStatus = ERROR;
      break;
    }				
  }

  //if something has gone wrong, stop the plan and return.
  if (mStatus == ERROR) {
    mPlanner->stopPlanner();
    mStatus = ERROR;
  } else {
    DBGA(mPlanner->getListSize() - mLastSolution << " solutions saved to database");
  }
  mLastSolution = mPlanner->getListSize();
}



/*!
  Store a grasp in the database. 
  Take the starting pose, refine it to a final grasp, and then
  store the final grasp parameters.
 */
bool GraspPlanningTask::saveGrasp(const GraspPlanningState *gps)
{


  GraspitDBModel* dbModel= mObject->getDBModel();
  assert(dbModel);
  
  //create new database grasp
  db_planner::Grasp* grasp = new db_planner::Grasp;
  
  std::vector<double> contacts = grasp->GetContacts();
  
  //store grasp meta-information
  grasp->SetSourceModel( *(static_cast<db_planner::Model*>(dbModel)) );
  grasp->SetHandName(GraspitDBGrasp::getHandDBName(mHand).toStdString());
  grasp->SetEpsilonQuality(0.0);
  grasp->SetVolumeQuality(0.0);
  grasp->SetEnergy(gps->getEnergy());
  
  grasp->SetSource("EIGENGRASPS_TASK_"+QString::number(mRecord.taskType).toStdString());
  
  //get the grasp parameters of the pregrasp
  std::vector<double> tempArray;
  //the posture
  for(int i = 0; i < gps->readPosture()->getNumVariables(); ++i){
	  tempArray.push_back(gps->readPosture()->readVariable(i));
  }
  grasp->SetPregraspJoints(tempArray);
  grasp->SetFinalgraspJoints(tempArray);
  
  //the position
  tempArray.clear();
  for(int i = 0; i < gps->readPosition()->getNumVariables(); ++i){
    tempArray.push_back(gps->readPosition()->readVariable(i));
  }

  //store the pregrasp as both the pre and final grasp.
  grasp->SetPregraspPosition(tempArray);
  grasp->SetFinalgraspPosition(tempArray);
  
  //contacts
  //for some reason, the grasp's contact vector gets initialized to a mess!
  tempArray.clear();
  grasp->SetContacts(tempArray);
  grasp->SetParams(mRecord.params);
  std::vector<db_planner::Grasp*> graspList;

  //Create a grasp list with this one list.
  graspList.push_back(grasp);

  //Store this grasp in the database.
  bool result = mDBMgr->SaveGrasps(graspList);
  delete grasp;
  return result;
}

/*!
  As the planner updates, alert the user to the current status of the planner.
 */
void GraspPlanningTask::plannerUpdated(){
  static double rate = 0;
  static double last_time = 0;
  static double last_step = 0;

 

  double diff_time = mPlanner->getRunningTime() - last_time;
  

  mRecord.params[mRecord.params.size() - 1] = mPlanner->getCurrentStep();
  mRecord.params[mRecord.params.size() - 2] = mPlanner->getRunningTime();

   rate = 4*rate;
 
   rate += (mPlanner->getCurrentStep() - last_step)/diff_time;

   last_step = mPlanner->getCurrentStep();
   last_time = mPlanner->getRunningTime();
   
   rate /= 5;
   

   mRecord.params[mRecord.params.size() - 3] = rate;
   
   db_planner::TaskRecord test;
   mDBMgr->GetTaskStatus(mRecord,test);
   if (!test.taskOutcomeName.compare("DONE")){
     std::cout << "Some other instance finished running; Exiting";
     exit(0);
   }
   DBGA("Step " << mPlanner->getCurrentStep() << " of " << mPlanner->getMaxSteps() << " Running Time " << mPlanner->getRunningTime() <<"of " << mPlanner->getMaxRunningTime() <<" Rate: " << rate);  
   mDBMgr->SetTaskStatus(mRecord,"RUNNING");
}
