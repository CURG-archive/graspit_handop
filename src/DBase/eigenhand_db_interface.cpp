#include "eigenhand_db_interface.h"



/* Creates new 3x3 diagonal matrices from a vector of doubles. These matrices are appended to the end
 * the output vector. Does nothing if the input is not an appropriate length to be diagonalized.
 * @param output - vector of mat3 type 3x3 matrices.
 * @param input - vector of doubles to diagonalize
 *
 * @returns nothing.
 */
void EigenHandLoader::diagonalize(std::vector<mat3> & output, std::vector<double> input)
{
  if (input.size()%3)
    return;
  for(int i = 0; i < input.size(); i+=3)
    {
      output.push_back(mat3::IDENTITY);
      output.back()[0] = input[i];
      output.back()[4] = input[i+1];
      output.back()[8] = input[i+2];
    }
}


/* Loads virtual contacts from a file for a single kinematic chain. 
 *
 *@param finger - The kinematic chain describing the finger
 *@param filename - The file containing the virtual contacts
 *@param fingerNumber - This is currently only used as a sanity check. a finger number < 0  is an error condition.
 */
bool EigenHandLoader::loadContactData(KinematicChain * finger, QString filename, int fingerNumber)
{

  // Open the file
  FILE *fp = fopen(filename.latin1(), "r");
  if (!fp) {
    std::cout<< "Could not open contact file " << filename.latin1();
    return 0;
  }
  
  int numContacts;
  VirtualContact *newContact;
  fscanf(fp,"%d",&numContacts);
  for (int i=0; i<numContacts; i++) 
    {
      newContact = new VirtualContact();
      newContact->readFromFile(fp);
      newContact->setFingerNum(fingerNumber);
      
      int f = fingerNumber;
      int l = newContact->getLinkNum();
      
      if ( f >= 0) {
	newContact->setBody(finger->getLink(l) );
	finger->getLink(l)->addVirtualContact( newContact );
      } else {
	fprintf(stderr,"Wrong finger number on contact!!!\n");
	delete newContact;
	continue;
      }
      newContact->computeWrenches(false,false);
    }
  return 1;
}


/* Helper function that sets the joint's base position
 * This places the kinematic chain at the appropriate position around the base of the hand.
 *
 * @param h - Pointer to the hand being created
 * @param fingerNumber - The index of the kinematic chain being added.
 */
void EigenHandLoader::setBaseJointPosition(Hand * h, unsigned int fingerNumber)
{  
  // Get base joint
  Joint * j = h->getChain(fingerNumber)->getJoint(0);
  
  // Calculate offset angle from database joint description
  double offsetAngle = hd->fingerBasePositions[fingerNumber]*M_PI/180.0;	

  // Set the offset angle of the joint
  j->setOffset(offsetAngle);	
  
  // Disable collisions between the palm and the first link.
  h->getWorld()->toggleCollisions(false, h->getChain(fingerNumber)->getLink(1), h->getPalm());
  

  // These calculations are probably obsolete. 
  //j->setMin(j->getMin()+offsetAngle);
  //if(j->getMin() > M_PI)
  // j->setMin(j->getMin() - 2*M_PI);
  
  //j->setMax(j->getMax() + offsetAngle);
  //if(j->getMax() > M_PI)
  // j->setMax(j->getMax() - 2*M_PI);

  // Set the current joint position to 0.0, given the new offset
  j->setVal(0.0);	
}


/* Setup the eigengrasps for this hand for the planner.  Currently
 * this simply sets all of the joints as independent in the planner, 
 * as we are not using eigengrasps.
 *
 * @param h - Pointer to the hand being created.
 */
void EigenHandLoader::setupEigengrasps(Hand * h)
{
    // Clear out existing eigengrasps -- This shouldn't be necessary.
    delete h->getEigenGrasps();

    // Set eigengrasps as trivial eigengrasps.
    h->setEigenGrasps(new EigenGraspInterface(h));
    h->getEigenGrasps()->setTrivial();
    h->showVirtualContacts(true);
}

bool EigenHandLoader::testDefaultCollisions(Hand * h)
{

  // Setting the transform is one of the easier ways to 
  // update the world's collision state. 
  h->setTran(transf::IDENTITY);
  CollisionReport colReport;
  h->getWorld()->getCollisionReport(&colReport);
  
  //transf test = translate_transf(vec3(0,0,100));
  //if !h->moveTo(test,1.0,1.0)
  if (colReport.size()){
    h->getWorld()->destroyElement(h,true);
    std::cout << "Failed to load hand -- collision in default pose\n";
      return false;
  }
}


Hand * EigenHandLoader::loadHand(World * w)
  {
    // Get the graspit root directory to compose the palm's path
    QString graspitRoot = getenv("GRASPIT");
    
    // Load the base hand with just the palm
    Hand * h = static_cast<Hand *>(w->importRobot(graspitRoot + "/models/robots/Eigenhand/EigenhandBase.xml"));
    
    // Get the diagonalized palm scaling matrix
    std::vector<mat3> output;
    diagonalize(output, hd->palmScale);
    
    // Scale the palm
    RobotTools::scalePalm(output[0], h);

    // Load the kinematic chains for the hand
    for(unsigned int i = 0; i < fdList.size(); ++i)
      {
	// Add the chain from the description
	h->addChain(loadKinematicChain(h, *fdList[i], i));

	// Set the location of the finger around the base
	setBaseJointPosition(h, i);
      }
    
    // Set up the eigengrasps for the hand
    setupEigengrasps(h);
    
    // Test that the default pose does not have collisions. If it does, this hand is not usable.
    if (!testDefaultCollisions(h))
      return NULL;

    // Set the hand's name appropriately. 
    h->setName(QString::number(hd->handID));

    // Return the finished hand.
    return h;
  }


void EigenHandLoader::addDOFSForKinematicChain(Hand * h, int numJoints)
{
  //When a hand is closed, the default velocity of each joint determines the joint trajectories of the hand.
  //The joints that twist the fingers laterally shouldn't move when the hand closes.
  
  // prototype for DOFs that do not move when the hand is closed
  // Other than the default velocity, these settings are arbitrary
  RigidDOF passiveDOF;
  passiveDOF.setDefaultVelocity(0);
  passiveDOF.setMaxEffort(6.0e7);
  passiveDOF.setKp(4.5e9);
  passiveDOF.setKv(4.5e5);
  
  //prototype for DOFS that do move when the hand is closed.
  RigidDOF activeDOF;
  activeDOF.setDefaultVelocity(1);
  activeDOF.setMaxEffort(5.0e9);
  activeDOF.setKp(1.0e11);
  activeDOF.setKv(1.0e7);
  
  //always add the DOF for rotation around the base of the palm and around 
  //the base of the finger    
  h->addDOF(new RigidDOF(passiveDOF));
  h->addDOF(new RigidDOF(passiveDOF));
  
  
  
  // for each additional link of the rest of the hand, add one active and one passive joint
  // The passive joint is for twisting around the joint.
  for(int i = 0; i < (numJoints-2)/2; ++ i)
    {
      h->addDOF(new RigidDOF(activeDOF));
      h->addDOF(new RigidDOF(passiveDOF));
    }
}

KinematicChain * EigenHandLoader::readKinematicChain(Hand * h, int numLinks, unsigned int chainNumber, int DOFOffset)
{

  //Set up path for finger
  QString graspitRoot = getenv("GRASPIT");
  
  QString fingerFileName = graspitRoot 
    + "/models/robots/Eigenhand Lite Model VRML/dynamic_link" 
    + QString::number(numLinks) 
    + QString(".xml");

  //Set up path for links
  QString linkdir(graspitRoot + QString("/models/robots/Eigenhand Lite Model VRML/iv/"));
  
  //Load xml document describing finger
  TiXmlDocument doc(fingerFileName);
  doc.LoadFile();
  const TiXmlElement * root = doc.RootElement();
  
  //Create kinematic chain
  KinematicChain * finger = new KinematicChain(h, chainNumber, h->getNumJoints());

  //Load the chain
  finger->initChainFromXml(root,  linkdir, DOFOffset);

  //Return the created finger.
  return finger;
}

void EigenHandLoader::setJointLimitsFromFD(Hand * h, KinematicChain * finger, const FingerDescription & fd, int DOFOffset)
{
    //Set the joints default value and limits    
    for(int i = 0; i < finger->getNumJoints(); ++i)
      {
	//set the joint limits and offset
	finger->getJoint(i)->setMin(fd.jointRangeList[2*i]*M_PI/180.0);
	finger->getJoint(i)->setMax(fd.jointRangeList[2*i + 1]*M_PI/180.0);
	finger->getJoint(i)->setVal(0);//(fd.jointRangeList[2*i]*M_PI/180.0 + fd.jointRangeList[2*i + 1]*M_PI/180.0)/2.0);
       
	std::list<Joint *> jlist;
	jlist.push_back(finger->getJoint(i));
	h->getDOF(DOFOffset + i)->initDOF(h, jlist);
	h->getDOF(DOFOffset + i)->setDOFNum(DOFOffset + i);
      }

}


void EigenHandLoader::getScalingMatrixListFromFD(KinematicChain * finger, 
						 const FingerDescription & fd, 
						 std::vector<mat3> & scalingMatrixList)
{
  //Create scaling matrix for each joint
  for(int i = 0; i < finger->getNumJoints(); ++i)
    {
      //create the scaling matrix	
	scalingMatrixList.push_back(mat3::IDENTITY);
    }
  // Set the scaling matrices
  scalingMatrixList[0][0] = fd.jointLenList[0];
  scalingMatrixList[2][8] = fd.jointLenList[3];
  scalingMatrixList[3][4] = fd.jointLenList[3];
  scalingMatrixList[4][8] = fd.jointLenList[5];
  scalingMatrixList[5][8] = fd.jointLenList[5];
}


KinematicChain * EigenHandLoader::loadKinematicChain(Hand *h , const FingerDescription & fd, unsigned int chainNumber)
  {     
    // Get the number of joints that are currently in the hand so that we know how far into the list to start
    // assigning DOFS to this kinematic chain.

    int DOFOffset = h->getNumDOF();

    // Create new DOFS for the kinematic chain.
    addDOFSForKinematicChain(h, fd.jointLenList.size());
    
    KinematicChain * finger = readKinematicChain(h, fd.jointLenList.size(), chainNumber, DOFOffset);
 
    // Create storage for scaling matrices. 
    std::vector<mat3> scalingMatrixList;

    //Set the joint limits from the finger description
    setJointLimitsFromFD(h, finger, fd, DOFOffset);
    
    //Set up the scaling matrices
    getScalingMatrixListFromFD(finger, fd, scalingMatrixList);

    // Get the graspit root directory to compose the virtual contacts paths
    QString graspitRoot = getenv("GRASPIT");

    //Set up the finger's virtual contacts file
    QString fingerContactFile = graspitRoot
      + "/models/robots/Eigenhand Lite Model VRML/virtual/dynamic_link_virtual_contacts"
      + QString::number(fd.jointLenList.size())
      + QString(".vgr");
    
    //Read the virtual contacts
    loadContactData(finger, fingerContactFile, chainNumber);
    
    //Scale the chain
    RobotTools::scaleChain(&scalingMatrixList[0], h->getPalm(), finger);
    //for(int i = 0; i < finger->getNumLinks() - 2; ++i)
      //      h->getWorld()->toggleCollisions(false, finger->getLink(i), finger->getLink(i+2));
    
    //Disable collisions with links near the palm.
    h->getWorld()->toggleCollisions(false, h->getPalm(), finger->getLink(2));
    h->getWorld()->toggleCollisions(false, h->getPalm(), finger->getLink(3));       
    
    return finger;    
  }

EigenHandLoader::~EigenHandLoader()
{
  delete hd;
  while( !fdList.empty() )
    {
      delete fdList.back();
      fdList.pop_back();
    }
}
