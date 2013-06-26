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
  bool loadContactData(KinematicChain * finger, QString filename, int fingerNumber)
{
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

//! Helper function to create a list of diagonal matrices from a list of doubles. 
void getDiagonalMatrices2(std::vector<mat3> & output, std::vector<double> input)
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






 public:  
  
  HandDescription * hd;
  std::vector<FingerDescription*> fdList;


  EigenHandLoader(){};
  
  ~EigenHandLoader()
    {
      delete hd;
      while( !fdList.empty() )
	{
	  delete fdList.back();
	  fdList.pop_back();
	}
    }
  
  Hand * loadHand(World * w)
  {
    
    QString graspitRoot = getenv("GRASPIT");
    
  
    Hand * h = static_cast<Hand *>(w->importRobot(graspitRoot + "/models/robots/Eigenhand/EigenhandBase.xml"));
    std::vector<mat3> output;
    getDiagonalMatrices2(output, hd->palmScale);
    RobotTools::scalePalm(output[0], h);

    for(unsigned int i = 0; i < fdList.size(); ++i)
      {
	h->addChain(loadKinematicChain(h, *fdList[i], i));
	Joint * j = h->getChain(i)->getJoint(0);
	double offsetAngle = hd->fingerBasePositions[i]*M_PI/180.0;	
	j->setOffset(offsetAngle);	
	
	h->getWorld()->toggleCollisions(false, h->getChain(i)->getLink(1), h->getPalm());

	//j->setMin(j->getMin()+offsetAngle);
	//if(j->getMin() > M_PI)
	// j->setMin(j->getMin() - 2*M_PI);
	
	//j->setMax(j->getMax() + offsetAngle);
	//if(j->getMax() > M_PI)
	// j->setMax(j->getMax() - 2*M_PI);
	j->setVal(0.0);	
      }
    
    
    delete h->getEigenGrasps();
    h->setEigenGrasps(new EigenGraspInterface(h));
    h->getEigenGrasps()->setTrivial();
    h->showVirtualContacts(true);
    h->setTran(transf::IDENTITY);
    CollisionReport colReport;
    h->getWorld()->getCollisionReport(&colReport);
    
    //transf test = translate_transf(vec3(0,0,100));
    //if !h->moveTo(test,1.0,1.0)
    if (colReport.size()){
      h->getWorld()->destroyElement(h,true);
      std::cout << "Failed to load hand -- collision in default pose\n";
      return NULL;
    }
    h->setName(QString::number(hd->handID));
    return h;
  }


  KinematicChain * loadKinematicChain(Hand *h , const FingerDescription & fd, unsigned int chainNumber)
  {
    
    int DOFOffset = h->getNumDOF();
    //prototype for DOFs that do not move when the hand is closed
    RigidDOF passiveDOF;
    passiveDOF.setDefaultVelocity(0);
    passiveDOF.setMaxEffort(6.0e7);
    passiveDOF.setKp(4.5e9);
    passiveDOF.setKv(4.5e5);
    
    
    RigidDOF activeDOF;
    activeDOF.setDefaultVelocity(1);
    activeDOF.setMaxEffort(5.0e9);
    activeDOF.setKp(1.0e11);
    activeDOF.setKv(1.0e7);

    //always add the DOF for rotation around the base of the palm and around 
    //the base of the finger    
    h->addDOF(new RigidDOF(passiveDOF));
    h->addDOF(new RigidDOF(passiveDOF));
    
    std::vector<mat3> scalingMatrixList;

    //for each additional link of the rest of the hand, add one active and one passive joint
    for(int i = 0; i < (fd.jointLenList.size()-2)/2; ++ i)
      {
	h->addDOF(new RigidDOF(activeDOF));
	h->addDOF(new RigidDOF(passiveDOF));
      }

    QString graspitRoot = getenv("GRASPIT");

    QString fingerFileName = graspitRoot 
                             + "/models/robots/Eigenhand Lite Model VRML/dynamic_link" 
                             + QString::number(fd.jointLenList.size()) 
                             + QString(".xml");
    
    TiXmlDocument doc(fingerFileName);
    doc.LoadFile();
    const TiXmlElement * root = doc.RootElement();

    KinematicChain * finger = new KinematicChain(h, chainNumber, h->getNumJoints());
    QString linkdir(graspitRoot + QString("/models/robots/Eigenhand Lite Model VRML/iv/"));
    finger->initChainFromXml(root,  linkdir, DOFOffset);
    //Set the joints default value and limits
    for(int i = 0; i < finger->getNumJoints(); ++i)
      {
	//set the joint limits and offset
	finger->getJoint(i)->setMin(fd.jointRangeList[2*i]*M_PI/180.0);
	finger->getJoint(i)->setMax(fd.jointRangeList[2*i + 1]*M_PI/180.0);
	finger->getJoint(i)->setVal(0);//(fd.jointRangeList[2*i]*M_PI/180.0 + fd.jointRangeList[2*i + 1]*M_PI/180.0)/2.0);


	//create the scaling matrix
	scalingMatrixList.push_back(mat3::IDENTITY);
	//scalingMatrixList.back()[4] = fd.jointLenList[i]; 
	std::list<Joint *> jlist;
	jlist.push_back(finger->getJoint(i));
	h->getDOF(DOFOffset + i)->initDOF(h, jlist);
	h->getDOF(DOFOffset + i)->setDOFNum(DOFOffset + i);
      }
    scalingMatrixList[0][0] = fd.jointLenList[0];
    scalingMatrixList[2][8] = fd.jointLenList[3];
    scalingMatrixList[3][4] = fd.jointLenList[3];
    scalingMatrixList[4][8] = fd.jointLenList[5];
    scalingMatrixList[5][8] = fd.jointLenList[5];

        QString fingerContactFile = graspitRoot
      + "/models/robots/Eigenhand Lite Model VRML/virtual/dynamic_link_virtual_contacts"
      + QString::number(fd.jointLenList.size())
      + QString(".vgr");

    loadContactData(finger, fingerContactFile, chainNumber);

    RobotTools::scaleChain(&scalingMatrixList[0], h->getPalm(), finger);
    for(int i = 0; i < finger->getNumLinks() - 2; ++i)
      //      h->getWorld()->toggleCollisions(false, finger->getLink(i), finger->getLink(i+2));
    h->getWorld()->toggleCollisions(false, h->getPalm(), finger->getLink(2));
    h->getWorld()->toggleCollisions(false, h->getPalm(), finger->getLink(3));
    


    return finger;    
  }




};





//!
#endif
