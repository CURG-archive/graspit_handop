#ifndef _GRASPPLANNINGSERVICE_H_
#define _GRASPPLANNINGSERVICE_H_

#include <QString>
#include <QObject>
#include <vector>

#include "matvec3D.h"

class ClientSocket;
class Hand;
class GraspPlanningState;
namespace db_planner {
	class DatabaseManager;
	class Model;
	class Grasp;
}

class GraspPlanningService : public QObject
{
	Q_OBJECT

private:
	QString mHandName, mObjectName, mMethodType, mMessage;
	ClientSocket* mSocket;
	transf mObjectPose;
	//! This list of grasps is the grasps from CGDB
	std::vector<db_planner::Grasp*> mGraspList, filteredGraspList;
	//! The list of models available in the dbase, as retrieved by the DBMgr
	std::vector<db_planner::Model*> mModelList;
	bool mIsParamSet;

	//! The mgr that all connections to the dbase have to go through
	db_planner::DatabaseManager *mDBMgr;
	Hand* mHand;

	void init();
	//store database information
	QString mdbaseURL, mdbaseUserName, mdbasePassword, mdbaseName;
	int mdbasePort;
	
	QString synthesizeMsg(std::vector<db_planner::Grasp*> grasps);
	QString extractNumbers(std::vector<double> numArray);
	
	vec3 mApproachVector;
	double mApproachAngle;
	void clearGraspList();
	db_planner::Model * dbmodel;
	//un-define the default constructor
	GraspPlanningService(){};

public:
	/* mObjectName specifies the object name in CGDB's scaled_model_name, mHandName specifies the hand name in CGDB, mObjectPose specifies the
       object's pose in some coordinate system, this service will transform the grasp to that coordinate system.
	*/

 GraspPlanningService(QString dbURL, QString dbName, QString dbPort, QString dbLogin, QString dbPassword): mIsParamSet(false), dbmodel(NULL), mdbaseURL(dbURL), mdbaseUserName(dbLogin), mdbasePassword(dbPassword), mdbaseName(dbName), mdbasePort(dbPort.toInt()), mHand(NULL), mDBMgr(NULL)
	{
	  //init();
	}
	void setParams(QString hand, QString object, QString method_type, ClientSocket* clientSocket, transf t, const vec3 & approach_vector, double approach_tolerance_angle);
	~GraspPlanningService(){}
	void retrieve();
	void plan_from_tasks();
	void transform();
	void check(const transf &);
	void rank();
	QString report();

};
#endif //_GRASPPLANNINGSERVICE_H_
