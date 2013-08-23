#ifndef EIGENHAND_DB_INTERFACE_H_
#define EIGENHAND_DB_INTERFACE_H_
#include "db_manager.h"
#include "robot.h"
#include "world.h"
#include "tinyxml.h"
#include "eigenGrasp.h"






struct HandDescription
{
  int handID;
  std::vector<double> palmScale;
  std::vector<unsigned int> fingerIDList;
  std::vector<double> fingerBasePositions;
  std::vector<unsigned int> generation;
};


struct FingerDescription
{
  int fingerID;
  //!
  std::vector<double> jointLenList;
 
  //! should be twice as long as jointLenList
  std::vector<double> jointRangeList;
};

class EigenHandLoader
{

 private:
  //! Loads virtual contacts from a file
  bool loadContactData(KinematicChain * finger, QString filename, int fingerNumber);

  //! Helper function to create a list of diagonal matrices from a list of doubles. 
  void diagonalize(std::vector<mat3> & output, std::vector<double> input);

  //! Helper function that sets the finger's base position around the palm
  void setBaseJointPosition(Hand * h, unsigned int fingerNumber);

  //! Helper function that sets up the eigengrasps for the hand.
  void setupEigengrasps(Hand * h);

  //! Helper function to sanity check that the hand created does not self collide in it's default pose. 
  bool testDefaultCollisions(Hand * h);

  //! Helper function to create new DOFs for the hand
  void addDOFSForKinematicChain(Hand * h, int numJoints);

  //! Helper function to read kinematic chain
  KinematicChain * readKinematicChain(Hand * h, int numLinks, unsigned int chainNumber, int DOFOffset);

  //! Helper function to set joint range from finger description
  void setJointLimitsFromFD(Hand * h, KinematicChain * finger, const FingerDescription & fd, int DOFOffset);

  //! Helper function to read the scaling matrix vector from the finger description
  void getScalingMatrixListFromFD(KinematicChain * finger, const FingerDescription & fd, 
				  std::vector<mat3> & scalingMatrixList);

 public:  
  
  HandDescription * hd;
  std::vector<FingerDescription*> fdList;
  

  EigenHandLoader(){};
  
  ~EigenHandLoader();
  
  //! Loads a hand whose description is already loaded in to the FingerDescription and hand description
  Hand * loadHand(World * w);
  
  //! Loads a Kinematic Chain from a KinematicChain description.
  KinematicChain * loadKinematicChain(Hand *h , const FingerDescription & fd, 
				      unsigned int chainNumber);

};





//!
#endif
