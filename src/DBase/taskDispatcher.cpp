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
// $Id: taskDispatcher.cpp,v 1.1 2009/10/08 16:13:11 cmatei Exp $
//
//######################################################################

#include "taskDispatcher.h"

#include <Inventor/sensors/SoTimerSensor.h>

#include "graspitGUI.h"
#include "DBPlanner/sql_database_manager.h"
#include "graspit_db_model.h"
#include "graspit_db_grasp.h"
#include "graspPlanningTask.h"
#include <QApplication>
#include <QHostInfo>
#include <QDir>

#include "debug.h"
#include "exitReturnCodes.h"

//common initialization code
inline void TaskDispatcher::init(){
//hard-coded for now
	mMaxTasks = -1;
	mCompletedTasks = 0;
}

TaskDispatcher::TaskDispatcher() : mFactory(*(new TaskFactory())), mDBMgr(NULL) , mCurrentTask(NULL), mSensor(NULL) 
{
	init();
}

TaskDispatcher::TaskDispatcher(TaskFactory * factory, int task_id): mFactory(*factory), mDBMgr(NULL), mCurrentTask(NULL), mSensor(NULL), mTaskID(task_id){
	init();
};

TaskDispatcher::~TaskDispatcher()
{
	if (mCurrentTask) {
		//this should not really happen
		DBGA("Dispatcher: deleting current task on cleanup");
		delete mCurrentTask;
	}
	delete mDBMgr;
	delete mSensor;
}

int TaskDispatcher::connect(std::string host, int port, std::string username, 
			   std::string password, std::string database) 
{
	delete mDBMgr;
	//careful: we pass a null for the grasp allocator as we don't know
	//yet which hand we'll be using
	mDBMgr = new db_planner::SqlDatabaseManager(host, port, username, password, database,
						    new GraspitDBModelAllocator(),new GraspitDBGraspAllocator(NULL));
	if (!mDBMgr->isConnected()) {
		DBGA("DBase operator: Connection failed");
		delete mDBMgr; mDBMgr = NULL;
		return -1;
	}
	return 0;
}

void TaskDispatcher::mainLoop()
{
	//check on the current task
	if (mCurrentTask) {
		switch (mCurrentTask->getStatus()) {
		case Task::RUNNING:
		  {
		    
		    break;
		  }
		case Task::ERROR:
			//mark the task as error in the database
			if (!mDBMgr->SetTaskStatus(mCurrentTask->getRecord(),"ERROR")) {
				DBGA("Dispatcher: error marking completed task");
				mStatus = ERROR;
			}
			delete mCurrentTask; mCurrentTask = NULL;
			exit(-1);
			break;
		case Task::DONE:
		  {
			//mark the task as completed in the database
			if (!mDBMgr->SetTaskStatus(mCurrentTask->getRecord(),"COMPLETED")) {
				DBGA("Dispatcher: error marking completed task");
				mStatus = ERROR;
			}
			mDBMgr->AgeTaskStatus(mCurrentTask->getRecord().taskType,"RUNNING","TO_GO",mCurrentTask->getRecord().taskTime + 30);
			if(mCurrentTask)
			  delete mCurrentTask; mCurrentTask = NULL;			
			
			if(mDBMgr)
			  delete mDBMgr;
			exit(0);
		  }
		}
	}
}

/*! Reads the next task to be started from the database. Does not return 
    an error code; rather, it sets its own status based on the result of
    the operation:
  
    - if no tasks are available to be started, or an error is encountered, 
    it will set its own status to NO_TASK or ERROR. 

    - if a task is started successfully, it will set its status to RUNNING.

    - if the preset number of tasks has been completed, sets status to DONE

    If the timer has not been initialized yet, it also initializes the timer,
    but only of the task has been started successfully.
*/
void TaskDispatcher::start()
{
	if (mMaxTasks >= 0 && mCompletedTasks >= mMaxTasks) {
		mStatus = DONE;
		return;
	}
	db_planner::TaskRecord rec;
	rec.taskType = mTaskID;

	mDBMgr->AgeTaskStatus(rec.taskType,"RUNNING","TO_GO", 30);

	if (!mDBMgr->GetNextTask(&rec,"TO_GO", "RUNNING")) {
		DBGA("Dispatcher: error reading next task");
		mStatus = ERROR;
		exit(5);
		return;
	}
	DBGA("Task_ID " << rec.taskId );
	//task type 0 is reserved for no task to do
	if (!rec.taskType) {
		DBGA("Dispatcher: no tasks to be executed");
		mStatus = NO_TASK;
		exit(NO_JOBS);
		return;
	}

    string dirname = "/home/jweisz/html/graspit_handop/servers/" + QHostInfo::localHostName().toStdString() +"/tasks/";
    QDir logdir(dirname.c_str());
    if(!logdir.exists())
        logdir.mkpath(".");

    assert(logdir.exists());

    string filename = dirname + "id_" + QString::number(rec.taskId).toStdString();
	freopen (filename.c_str(), "w",stdout);
	freopen (filename.c_str(), "a",stderr);
	std::cout <<" Process id:" <<  getpid() << "\n";

	mCurrentTask = mFactory.getTask(this, mDBMgr,rec);
	if (!mCurrentTask) {
		DBGA("Dispatcher: can not understand task type: " << rec.taskType);
		mStatus = ERROR;
		exit(-1);
		return;
	}
	mCurrentTask->start();
	if (mCurrentTask->getStatus() == Task::RUNNING) {
		mStatus = RUNNING;
		DBGA("Dispatcher: started task of type " << rec.taskType);
	} else {
		mStatus = ERROR;
		if (!mDBMgr->SetTaskStatus(mCurrentTask->getRecord(),"ERROR")) {
		  DBGA("Dispatcher: error marking completed task");
		  mStatus = ERROR;
		}
		if (mCurrentTask){
		  delete mCurrentTask; mCurrentTask = NULL;
		}
		DBGA("Dispatcher: error starting task of type " << rec.taskType);
		
	}
	if(mStatus == RUNNING || mStatus == ERROR) {
		if (!mSensor) {
			mSensor = new SoTimerSensor(sensorCB, this);
			mSensor->setInterval( SbTime( 3.0 ));
			mSensor->schedule();			
		}
	}
}

void TaskDispatcher::sensorCB(void *data, SoSensor*)
{
	TaskDispatcher *dispatch = static_cast<TaskDispatcher*>(data);
	dispatch->mainLoop();
}

Task* TaskFactory::getTask(TaskDispatcher *op, db_planner::DatabaseManager *mgr, 
			   db_planner::TaskRecord rec)
{
	switch(rec.taskType) {
	case 1:
		return new GraspPlanningTask(op, mgr, rec);
		//return new EmptyTask(op, mgr, rec);
	default:
		return NULL;
	}
}

void EmptyTask::start()
{
	mSensor = new SoTimerSensor(sensorCB, this);
	mSensor->setInterval( SbTime( 4.0 ));
	mSensor->schedule();			
	mStatus = RUNNING;
	DBGA("Empty task has started");
}

void EmptyTask::finish() 
{
	DBGA("Empty task has finished");
	mStatus = DONE;
}

EmptyTask::~EmptyTask() 
{
	DBGA("Empty task deleted");
	delete mSensor;
}

void EmptyTask::sensorCB(void *data, SoSensor*)
{
	EmptyTask *task = static_cast<EmptyTask*>(data);
	task->finish();
}
