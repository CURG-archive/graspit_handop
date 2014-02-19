#include "graspPlanningService.h"

#include <set>
#include <string>
#include <algorithm>

#include "searchState.h"
#include "debug.h"

#include "graspitServer.h"
#include "robot.h"
#include "world.h"
#include "DBPlanner/sql_database_manager.h"
#include "graspit_db_model.h"
#include "graspit_db_grasp.h"
#include "searchEnergy.h"
#include "graspPlanningTask.h" 
#include "egPlannerUtils.h"
#include "graspAnalyzingTask.h"
#include "harvardHandPlanningTask.h"
#include "DBase/genericGraspPlanningTask.h"
#include "exitReturnCodes.h"

bool compareGraspQM(db_planner::Grasp* g1, db_planner::Grasp* g2)
{
	return g1->EpsilonQuality() > g2->EpsilonQuality();
}

void GraspPlanningService::init()
{
	mDBMgr = new db_planner::SqlDatabaseManager(mdbaseURL.toStdString(),
		mdbasePort,
		mdbaseUserName.toStdString(),
		mdbasePassword.toStdString(),
		mdbaseName.toStdString(),
		new GraspitDBModelAllocator(),
		new GraspitDBGraspAllocator(mHand));

	if (mDBMgr->isConnected()) {
		std::cout << "CGDB connected" << std::endl;
	}
}

void GraspPlanningService::setParams(QString hand, QString object, QString method_type, ClientSocket* clientSocket, transf t, const vec3 & approach_vector, double approach_tolerance_angle)
{
	//import a new plan parameters
	mHandName = hand;
	mObjectName = object;
	mMethodType = method_type;
	mSocket = clientSocket;
	mObjectPose = t;
	mIsParamSet = true;
	mApproachVector = approach_vector;
	mApproachAngle = approach_tolerance_angle;
	clearGraspList();
	
}

void GraspPlanningService::clearGraspList()
{
	for(size_t i = 0; i < mGraspList.size(); ++i)
		delete mGraspList[i];
	for(size_t i = 0; i < filteredGraspList.size(); ++i)
		delete filteredGraspList[i];
	mGraspList.clear();
	filteredGraspList.clear();
}


QString GraspPlanningService::report()
{
	//make these params as junk
	mIsParamSet = false;

	mMessage = synthesizeMsg(filteredGraspList);
	if(!strcmp(mMethodType.latin1(), "RETRIEVAL"))
	{
		return mMessage;
	}
	else
	{
		std::cout << "Only RETRIEVAL method is supported so far" << std::endl;
		return QString();
	}
}

void GraspPlanningService::transform()
{
	transf prePosition, transformedPrePosition, finalPosition, transformedFinalPosition;
	std::vector<double> tmp;

	for(size_t i = 0; i < filteredGraspList.size(); ++i)
	{
		//get the pre-grasp position, x,y,z,qw,qx,qy,qz
		tmp = filteredGraspList[i]->GetPregraspPosition();
		prePosition = transf(Quaternion(tmp[3],tmp[4],tmp[5],tmp[6]), vec3(tmp[0],tmp[1],tmp[2]));

		//get the final-grasp position, x,y,z,qw,qx,qy,qz
		tmp = filteredGraspList[i]->GetFinalgraspPosition();
		finalPosition = transf(Quaternion(tmp[3],tmp[4],tmp[5],tmp[6]), vec3(tmp[0],tmp[1],tmp[2]));

		//calculate the transformed positions
		transformedPrePosition = prePosition * mObjectPose;
		transformedFinalPosition = finalPosition * mObjectPose;

		//store back the transformed position
		tmp.clear();
		tmp.push_back(transformedPrePosition.translation().x());
		tmp.push_back(transformedPrePosition.translation().y());
		tmp.push_back(transformedPrePosition.translation().z());
		tmp.push_back(transformedPrePosition.rotation().w);
		tmp.push_back(transformedPrePosition.rotation().x);
		tmp.push_back(transformedPrePosition.rotation().y);
		tmp.push_back(transformedPrePosition.rotation().z);
		filteredGraspList[i]->SetPregraspPosition(tmp);

		//store back the transformed position
		tmp.clear();
		tmp.push_back(transformedFinalPosition.translation().x());
		tmp.push_back(transformedFinalPosition.translation().y());
		tmp.push_back(transformedFinalPosition.translation().z());
		tmp.push_back(transformedFinalPosition.rotation().w);
		tmp.push_back(transformedFinalPosition.rotation().x);
		tmp.push_back(transformedFinalPosition.rotation().y);
		tmp.push_back(transformedFinalPosition.rotation().z);
		filteredGraspList[i]->SetFinalgraspPosition(tmp);
	}
}

void GraspPlanningService::retrieve()
{	
  DBGA("check hand");
	if (!mHand || GraspitDBGrasp::getHandDBName(mHand) != mHandName){
		if(mHand) 
			delete mHand;
   DBGA("To load hand");
		// if the hand name contains a '_', the name of the hand is the first part, the material is the second part
		if(!(mHand = GraspitDBGrasp::loadHandFromDBName(mHandName)))
			DBGA("GraspPlanningService: Invalid hand name: " + mHandName.toStdString());
	}
	// initialization must be done after setting of mHand if we want to retrieve models through this
	//DBMgr later, because the grasp allocator for the DBMgr must know its hand type
	if (!mDBMgr)
	  init();
	DBGA("To retrieve model list");
	//load the models from database manager
	if(!mDBMgr->ModelList(&mModelList,db_planner::FilterList::NONE)){
		DBGA("Model list retrieval failed");
		return;
	} else {
    DBGA("Model list retrieval succeeded");
  }
	//find the model
  DBGA("To find the model");
	for(size_t i = 0; i < mModelList.size(); ++i)
	{
		if( !strcmp(mModelList[i]->ModelName().c_str(), mObjectName.latin1()) ) //find the object
		{
			dbmodel = mModelList[i];
		}
	}

	if(!dbmodel)
	{
		std::cout << "object not found" << std::endl;
		return;
	}

	if(!mDBMgr->GetGrasps(*dbmodel,GraspitDBGrasp::getHandDBName(mHand).toStdString(), &mGraspList)){
		DBGA("Load grasps failed");
		mGraspList.clear();
		return;
	}
	std::cout << "grasps retrieved: " << mGraspList.size() << std::endl;
}

QString GraspPlanningService::synthesizeMsg(std::vector<db_planner::Grasp*> grasps)
{
	QString msg, quality;
	//brace for a whole message
	msg = QString("{");
	for(size_t i = 0; i < grasps.size(); ++i) //grasps.size()
	{
		//bracket for a pre-grasp
		msg += QString("[");
		quality.setNum(grasps[i]->EpsilonQuality());
		msg += quality;
		msg += QString(",");
		quality.setNum(grasps[i]->VolumeQuality());
		msg += quality;
		msg += QString(",");
		msg += extractNumbers(grasps[i]->GetPregraspPosition());
		msg += QString(",");
		msg += extractNumbers(grasps[i]->GetPregraspJoints());
		msg += QString("]");

		//bracket for a fin-grasp
		msg += QString("[");
		quality.setNum(grasps[i]->EpsilonQuality());
		msg += quality;
		msg += QString(",");
		quality.setNum(grasps[i]->VolumeQuality());
		msg += quality;
		msg += QString(",");

		msg += extractNumbers(grasps[i]->GetFinalgraspPosition());
		msg += QString(",");
		msg += extractNumbers(grasps[i]->GetFinalgraspJoints());
		msg += QString("]");
	}
	msg += QString("}");

	return msg;
}

QString GraspPlanningService::extractNumbers(std::vector<double> numArray)
{
	QString msg, tmp;
	//msg = QString("(");
	for(size_t i = 0; i < numArray.size(); ++i)
	{
		tmp.setNum(numArray[i]);
		msg += tmp;
		msg += (i == numArray.size() - 1) ? QString("") : QString(",");
	}
	return msg;
}

void GraspPlanningService::check(const transf & table_pose){
	filteredGraspList.clear();

  //load table
	Body * table = graspItGUI->getIVmgr()->getWorld()->importBody("Body", QString(getenv("GRASPIT"))+ QString("/models/obstacles/zeroplane.xml"));
	table->setTran(table_pose /** transf(Quaternion(.7071, .7071 , 0, 0), vec3(0,0,0))*/);
	//load the object
	GraspitDBModel* model = dynamic_cast<GraspitDBModel*>(dbmodel);
	//check that this model is already loaded into Graspit, if not, load it
	if (!model->geometryLoaded()) {
		//this loads the actual geometry in the scene graph of the object
		if ( model->load(graspItGUI->getIVmgr()->getWorld()) != SUCCESS) {
			DBGA("Model load failed");
			return;
		}
	}
	GraspableBody * mObject = model->getGraspableBody();
	graspItGUI->getIVmgr()->getWorld()->addBody(model->getGraspableBody());
  //adds the object to the collision detection system
	mObject->addToIvc();
	mObject->setTran(mObjectPose);
//  if(graspItGUI->getIVmgr()->getWorld()->noCollision())
//  {
//    std::cout << "no collision";
//  }
  graspItGUI->getIVmgr()->getWorld()->toggleCollisions(false, table, model->getGraspableBody());

	//todo: where to dynamic information come from?
	//model->getGraspableBody()->initDynamics();
	//this adds the object to the graspit world so that we can see it
	//graspItGUI->getIVmgr()->getWorld()->addBody(model->getGraspableBody());
  //create search grasp analyzer
  //SearchEnergy searchEnergy;
  //searchEnergy.setType(ENERGY_CONTACT_AUTOGRASP);
  //searchEnergy.disableRendering(false);
	//If SCALING OF OBJECT IS DESIRED THIS IS THE RIGHT PLACE
  for (int useFilter = 1; useFilter > -1 && filteredGraspList.size()==0; useFilter--){
  for( unsigned int j =0; j < mGraspList.size(); ++j){
    vec3 prePos = vec3(mGraspList[j]->GetPregraspPosition()[0],mGraspList[j]->GetPregraspPosition()[1],mGraspList[j]->GetPregraspPosition()[2]);
    vec3 finPos = vec3(mGraspList[j]->GetFinalgraspPosition()[0],mGraspList[j]->GetFinalgraspPosition()[1],mGraspList[j]->GetFinalgraspPosition()[2]);
    vec3 distVec = finPos - prePos;
    double backOffDist = distVec.len() - 60.0;

    /*these objects are symmetric around Z axis-- rotate the grasp every fifteen degrees and try again */

    for (double angle = 0; angle < 2.0*M_PI; angle += model->SymmetryAxis()[3]){
      //    std::cout << mGraspList[j]->GraspId() << std::endl;

      GraspPlanningState state(static_cast<GraspitDBGrasp*>(mGraspList[j])->getPreGraspPlanningState());
      state.setObject(mObject);
      state.setRefTran(mObjectPose);
      state.getPosition()->setTran(state.getPosition()->getCoreTran() *rotate_transf(angle, vec3 (model->SymmetryAxis()[0],model->SymmetryAxis()[1],model->SymmetryAxis()[2])));
      
      
      /*if(acos((vec3::Z*mHand->getApproachTran())*state.getTotalTran()%mApproachVector) > mApproachAngle)
	{
	DBGA("Maximum angle exceeded");
	  continue;
	  }*/
      
      
      /*Check that approach vector is in quadrant with positive negative y, positive x, positive z */

      vec3 approachVec = (vec3::Z*mHand->getApproachTran())* state.getTotalTran();
      if (useFilter && approachVec.z() > -.9 && (approachVec.z() > 0 || acos(approachVec%(vec3::X)) > M_PI/3.0)){
	std::cout << " Maximum angle breached" <<std::endl;
	continue;
	}
      if(!useFilter)
	std::cout << "No Filter Used" <<std::endl;
      
      double energy;
      bool legal = true;
      
      //    state.execute();
      //    graspItGUI->getIVmgr()->getWorld()->findAllContacts();
      //    if(!graspItGUI->getIVmgr()->getWorld()->noCollision(mHand))
      //    {
      //      std::cout << "collision in pregrasp" << std::endl;
      //      continue;
      //    }
	  //    if(j == 1) return;
	  //    searchEnergy.analyzeState(legal, energy, &state, false);
      
      //      mHand->getWorld()->findAllContacts();
      state.execute();

      legal = mHand->getNumContacts(table) == 0;
      if(!useFilter || legal){
	//move the pregrasp position back
	vec3 p = (state.getTotalTran().translation() - mHand->getTran().translation());
	//	double backOffDist = mHand->getApproachDistance(mObject, 100) - 60;
	state.getPosition()->setTran(translate_transf(vec3(0,0,backOffDist))*state.getPosition()->getCoreTran());
	state.execute();

	if (mHand->getWorld()->noCollision(mHand)){
	  GraspitDBGrasp * ng = new GraspitDBGrasp(*static_cast<GraspitDBGrasp*>(mGraspList[j]));
	  ng->setPreGraspPlanningState(new GraspPlanningState(&state));
	  ng->getFinalGraspPlanningState()->setRefTran(mObject->getTran());
	  ng->getFinalGraspPlanningState()->getPosition()->setTran(ng->getFinalGraspPlanningState()->getPosition()->getCoreTran() * rotate_transf(angle, vec3 (model->SymmetryAxis()[0],model->SymmetryAxis()[1],model->SymmetryAxis()[2])) );
	  ng->setFinalGraspPlanningState(new GraspPlanningState(ng->getFinalGraspPlanningState()));	  
	  filteredGraspList.push_back(ng);	  
	}
      }
	  else{
	    DBGA("Grasp Failed:" << j);
	    if (!legal) DBGA("Illegal grasp");
	    if(state.getEpsilonQuality() <= 0) 
	      DBGA(" Epsilon Quality < 0");
	  }
	  //    std::cout << "checking grasp: " << j << std::endl;
	    }
	}
  }
		 
	  graspItGUI->getIVmgr()->getWorld()->destroyElement(table, true);	
	  graspItGUI->getIVmgr()->getWorld()->destroyElement(mObject, false);	
	  table = NULL;
	  
	}
	
void GraspPlanningService::rank()
{
	std::vector<db_planner::Grasp*>::iterator first, last;
	first = filteredGraspList.begin();
	last = filteredGraspList.end();
	sort(first, last, compareGraspQM);
}

void GraspPlanningService::plan_from_tasks(){
/*Tasks know their own objects and hands
  In this case, we reuse the object parameter as the task type
*/
	if (!mDBMgr)
	  init();
	if(!mDBMgr->isConnected()){
	  //for now this error is fatal, quit.
	  DBGA("GraspPlanningService: Fatal error.  Not able to connect to CGDB");
	  exit(FAILED_TO_CONNECT_TO_DBASE);
	}else{
	  	  DBGA("Grasp planning service was able to connect");
	}
	  
	vector <string> taskNameList;
	mDBMgr->TaskTypeList(&taskNameList);
	//find task id - a QStringList would have this function built in.
	int task_type_id = -1;
	unsigned int titer;
	for(titer = 0; titer < taskNameList.size(); ++titer){
		if(!mObjectName.toStdString().compare(taskNameList[titer])){
			task_type_id	= static_cast<signed int>(titer)+1; //task_type_id is 1 indexed
			break;
		}
	}
	if (task_type_id < 0){
		DBGA("Couldn't find task name");
		exit(WRONG_JOB_TYPE);
	}
	TaskFactory * tf(NULL);
	//make the appropriate type of task factory for the task

	switch(task_type_id)
	  {
	  case 3:
	    {
	      tf = new GenericGraspPlanningTaskFactory<egPlannerUtils::GuidedPlannerFactory, egPlannerUtils::GuidedPlannerSaver>(mDBMgr,task_type_id, QString(taskNameList[titer].c_str()));
	    }
	  case 4:
	    {
	      tf = new GenericGraspPlanningTaskFactory<egPlannerUtils::SimAnPlannerFactory, egPlannerUtils::SimAnPlannerSaver>(mDBMgr,task_type_id, QString(taskNameList[titer].c_str()));
	    }
	  }	
	TaskDispatcher * td = new TaskDispatcher(tf, task_type_id);
	if(td->connect(mdbaseURL.toStdString(),
		       mdbasePort,
		       mdbaseUserName.toStdString(),
		       mdbasePassword.toStdString(),
		       mdbaseName.toStdString())){
	  //connect returns 0 on success - if this failed, print out that
	  //it failed and exit with an exit code
	  //FIXME exit codes
	  DBGA("GraspPlanningService: Fatal error.  Task Dispatcher not able to connect to CGDB");
	  exit(FAILED_TO_CONNECT_TO_DBASE);
	}
	/*otherwise, aknowledge that we have connected and 
	*started
	*/
	DBGA("Connected to task dispatching database - starting dispatcher");
	
	td->start();
	
	//for now this just leaks and runs until terminating the program
}
