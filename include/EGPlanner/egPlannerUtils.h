#ifndef EGPLANNER_UTILS_H
#define EGPLANNER_UTILS_H
#include "searchState.h"
#include "graspPlanningTask.h"
#include "loopPlanner.h"

class EGPlanner;
class Quaternion;
class Hand;
class Body;
class GraspitDBModel;
class vec3;
 
/*! Assorted utility functions for creating planners with various properties
 * and helping them interact with the CGDB
*/

namespace egPlannerUtils{
  //! Creates a GraspPlanningState that fixes the y-axis to be parallel to the current
  inline GraspPlanningState * gpsWithYParallelToCurrentY(Hand * h, const Body * const refBody);
  
  //! Gets a transform that rotates vector A on to vector B.  Assumes normalised vectors
  inline Quaternion transV1OnToV2(const vec3 &v1, const vec3 &v2);
  
  //! Align the hand to a vector in world coordinates
  bool alignHandYToV(Hand * h, vec3 & handVector, const vec3 & targetVector);
  
  
  //! Base class for planner factories
  class PlannerFactory
  {
  protected:
    db_planner::DatabaseManager & mDBMgr;
  public:
    PlannerFactory(db_planner::DatabaseManager * dbm) : mDBMgr(*dbm){};
    virtual EGPlanner * newPlanner(Hand * mHand, GraspitDBModel * m) = 0;
  };
  
  //! Factory for simulated annealing planners
  class SimAnPlannerFactory: public PlannerFactory
  {
  public:
    SimAnPlannerFactory(db_planner::DatabaseManager * dbm):PlannerFactory(dbm){};
    virtual EGPlanner * newPlanner(Hand * mHand, GraspitDBModel * m);
    
  };
  
  //! Factory for guided planners
  class GuidedPlannerFactory : public PlannerFactory
  {
  public:
  GuidedPlannerFactory(db_planner::DatabaseManager * dbm):PlannerFactory(dbm){};
    virtual EGPlanner * newPlanner(Hand * mHand, GraspitDBModel * m);
		
  };
  
  
  
  //! Base class for functors that save grasps to a database
  class PlannerSaver
  {
  protected:
    //! The manager to an open database. 
    db_planner::DatabaseManager & mDBMgr;
    
    //! The task identifier for the task type
    int mTaskNum;

    //! Name of task identifier
    QString mSource;
  public:
  PlannerSaver(db_planner::DatabaseManager * dbm, const int taskNum, QString source) 
    : mDBMgr(*dbm), mTaskNum(taskNum), mSource(source){};
    
    //! Save a list of grasps from an EGPlanner to the database 
    virtual bool saveGraspList(EGPlanner * finishedPlanner) = 0;
  };
  
  
  //! Functor class for saving guided planner results
  class GuidedPlannerSaver : public PlannerSaver
  {    
  public:
    GuidedPlannerSaver(db_planner::DatabaseManager * dbm, const int taskNum, QString source)
      : PlannerSaver(dbm, taskNum, source){};
     
    //! Save a list of grasps from an EGPlanner to the database 
    virtual bool saveGraspList(EGPlanner * finishedPlanner);
  };


  //Functor class for simulated annealing planner results
  class SimAnPlannerSaver : public PlannerSaver{
  public:
  SimAnPlannerSaver(db_planner::DatabaseManager * dbm, const int taskNum, QString source)
    : PlannerSaver(dbm, taskNum, source){};
    
    //! Save a list of grasps from an EGPlanner to the database 
    virtual bool saveGraspList(EGPlanner * finishedPlanner);
  };


}

#endif
