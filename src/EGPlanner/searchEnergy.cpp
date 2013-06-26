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
// Author(s): Matei T. Ciocarlie
//
// $Id: searchEnergy.cpp,v 1.42 2009/09/13 19:57:38 hao Exp $
//
//######################################################################

#include "searchEnergy.h"

#include <time.h>

#include "robot.h"
#include "barrett.h"
#include "body.h"
#include "grasp.h"
#include "contact.h"
#include "world.h"
#include "quality.h"
#include "searchState.h"
#include "graspitGUI.h"
#include "ivmgr.h"
#include "matrix.h"


//#define GRASPITDBG
#include "debug.h"

//#define PROF_ENABLED
#include "profiling.h"

PROF_DECLARE(QS);

//todo move this out of here
const double unbalancedForceThreshold = 1.0e10;

SearchEnergy::SearchEnergy()
{
	mHand = NULL;
	mObject = NULL;
	mType = ENERGY_CONTACT; //default
	mContactType = CONTACT_LIVE; //default
	mVolQual = NULL;
	mEpsQual = NULL;
	mDisableRendering = true;
	mOut = NULL;
}

void
SearchEnergy::createQualityMeasures()
{
	if (mVolQual) delete mVolQual;
	if (mEpsQual) delete mEpsQual;
	mVolQual = new QualVolume( mHand->getGrasp(), QString("SimAnn_qvol"),"L1 Norm");
	mEpsQual = new QualEpsilon( mHand->getGrasp(), QString("SimAnn_qeps"), "L1 Norm");
	DBGP("Qual measures created");
}

void
SearchEnergy::setHandAndObject(Hand *h, Body *o)
{
	if (mHand != h) {
		mHand = h;
		createQualityMeasures();
	}
	mObject = o;
}

SearchEnergy::~SearchEnergy()
{
	delete mVolQual;
	delete mEpsQual;
}

bool
SearchEnergy::legal() const
{	
	//hack for iros09
	//the compliant planners do their own checks
	if (mType == ENERGY_COMPLIANT || mType == ENERGY_DYNAMIC) return true;

	//no check at all
	//return true;
	
	//full collision detection
	//if the hand is passed as an argument, this should only check for collisions that
	//actually involve the hand
	return mHand->getWorld()->noCollision(mHand);
	
	/*
	//check only palm
	if ( mHand->getWorld()->getDist( mHand->getPalm(), mObject) <= 0) return false;
	return true;
	*/
}

void
SearchEnergy::analyzeCurrentPosture(Hand *h, Body *o, bool &isLegal, double &stateEnergy, bool noChange)
{
	setHandAndObject(h,o);
	
	if (noChange) {
		h->saveState();
	}

	if ( !legal() ) {
		isLegal = false;
		stateEnergy = 0;
	} else {
		isLegal = true;
		stateEnergy = energy();
	}

	if (noChange) {
		h->restoreState();
	}
}

void SearchEnergy::analyzeState(bool &isLegal, double &stateEnergy, const GraspPlanningState *state, bool noChange)
{
	Hand *h = state->getHand();
	setHandAndObject( h, state->getObject() );
	h->saveState();
	transf objTran = state->getObject()->getTran();

	bool render = h->getRenderGeometry();
	if( mDisableRendering) {
		h->setRenderGeometry(false);
	}

	if ( !state->execute() || !legal() ) {
		isLegal = false;
		stateEnergy = 0;
	} else {
		isLegal = true;
		stateEnergy = energy();
	}

	if (noChange || !isLegal) {
		h->restoreState();
		state->getObject()->setTran(objTran);
	}
	
	if (render && mDisableRendering) h->setRenderGeometry(true);	
	return;
}


double SearchEnergy::energy() const
{
	/*
		this is if we don't want to use pre-specified contacts, but rather the closest points between each link
		and the object all iterations. Not necessarily needed for contact energy, but useful for GQ energy
	*/
	if (mContactType == CONTACT_LIVE && mType != ENERGY_AUTOGRASP_QUALITY && mType != ENERGY_STRICT_AUTOGRASP) {
		mHand->getWorld()->findVirtualContacts(mHand, mObject);
		DBGP("Live contacts computation");
	}

	double e;
	switch (mType) {
		case ENERGY_CONTACT:
			mHand->getGrasp()->collectVirtualContacts();
			e = contactEnergy();
			break;
		case ENERGY_POTENTIAL_QUALITY:
			mHand->getGrasp()->collectVirtualContacts();
			e = potentialQualityEnergy();
			break;
		case ENERGY_AUTOGRASP_QUALITY:
			// this one will collect REAL contacts after autograsp is completed
			e = autograspQualityEnergy();
			break;
		case ENERGY_CONTACT_QUALITY:
			mHand->getGrasp()->collectVirtualContacts();
			e = guidedPotentialQualityEnergy();
			break;
		case ENERGY_GUIDED_AUTOGRASP:
			// we let this one collect its contact explicitly since is has to do it twice
			e = guidedAutograspEnergy();
			break;
		case ENERGY_STRICT_AUTOGRASP:
			// this one will collect REAL contacts after autograsp is completed
			e = strictAutograspEnergy();
			break;
		case ENERGY_CONTACT_AUTOGRASP:
		// this one will collect REAL contacts after autograsp is completed
			e = approachToContactAutograspQualityEnergy();
			break;
		case ENERGY_COMPLIANT:
			e = compliantEnergy();
			break;
		case ENERGY_DYNAMIC:
			e = dynamicAutograspEnergy();
			break;
		case NUM_CONTACTS:
			e = numContactsEnergy();
			break;
	        case ENERGY_GFO:
		        e = gfoEnergy();
			break;
	        case CONTACT_GFO:
		        mHand->getGrasp()->collectVirtualContacts();
       		        e = contactGfoEnergy();
			break;			  	

		default:
			fprintf(stderr,"Wrong type of energy requested!\n");
			e = 0;
	}
	return e;
}

double
SearchEnergy::contactEnergy() const
{
	//DBGP("Contact energy computation")
	//average error per contact
	VirtualContact *contact;
	vec3 p,n,cn;
	double totalError = 0;
	for (int i=0; i<mHand->getGrasp()->getNumContacts(); i++) {
		contact = (VirtualContact*)mHand->getGrasp()->getContact(i);
		contact->getObjectDistanceAndNormal(mObject, &p, NULL);

		double dist = p.len();
		//this should never happen anymore since we're never inside the object
		//if ( (-1.0 * p) % n  < 0) dist = -dist;
	
		//BEST WORKING VERSION, strangely enough
		
		//let's try this some more
		//totalError += distanceFunction(dist);
		//cn = -1.0 * contact->getWorldNormal();
		
		//new version
		cn = contact->getWorldNormal();		  
		n = normalise(p);
		double d = 1 - cn % n;
		if (cn % p < 0)
		  d *= 1e5;
		totalError += d * 200.0 / 2.0;
		totalError += fabs(dist);
	}
	
	

	totalError /= mHand->getGrasp()->getNumContacts();
	//DBGP("Contact energy: " << totalError);
		
	return totalError;
}




/*!	This formulation combines virtual contact energy with autograsp energy. Virtual contact energy is used to "guide"
	initial	stages of the search and to see if we should even bother computing autograsp quality. Autograsp is a couple
	of orders of magnitude higher and so should work very well with later stages of the sim ann search
*/
double
SearchEnergy::guidedAutograspEnergy() const
{
	//first compute regular contact energy; also count how many links are "close" to the object
	VirtualContact *contact;
	vec3 p,n,cn;
	double virtualError = 0; int closeContacts=0;

	//collect virtual contacts first
	mHand->getGrasp()->collectVirtualContacts();
	for (int i=0; i<mHand->getGrasp()->getNumContacts(); i++) {

		contact = (VirtualContact*)mHand->getGrasp()->getContact(i);
		contact->getObjectDistanceAndNormal(mObject, &p, &n);

		double dist = p.len();
		if ( (-1.0 * p) % n  < 0) dist = -dist;
	
		//BEST WORKING VERSION, strangely enough
		virtualError += fabs(dist);
		cn = -1.0 * contact->getWorldNormal();
		double d = 1 - cn % n;
		virtualError += d * 100.0 / 2.0;

		if ( fabs(dist)<20 && d < 0.3 ) closeContacts++;
	}
	
	virtualError /= mHand->getGrasp()->getNumContacts();

	//if more than 2 links are "close" go ahead and compute the true quality
	double volQuality = 0, epsQuality = 0;
	if (closeContacts >= 2) {
		mHand->autoGrasp(false, 1.0);
		//now collect the true contacts;
		mHand->getGrasp()->collectContacts();
		if (mHand->getGrasp()->getNumContacts() >= 4) {
			mHand->getGrasp()->updateWrenchSpaces();
			volQuality = mVolQual->evaluate();
			epsQuality = mEpsQual->evaluate();
			if (epsQuality < 0) epsQuality = 0; //QM returns -1 for non-FC grasps
		}

		DBGP("Virtual error " << virtualError << " and " << closeContacts << " close contacts.");
		DBGP("Volume quality: " << volQuality << " Epsilon quality: " << epsQuality);		
	}

	//now add the two such that the true quality is a couple of orders of magn. bigger than virtual quality
	double q;
	if ( volQuality == 0) q = virtualError;
	else q = virtualError - volQuality * 1.0e3;
	if (volQuality || epsQuality) {DBGP("Final quality: " << q);}

	//DBGP("Final value: " << q << std::endl);
	return q;
}

/*!	This version uses the contact energy to guide the search when quality energy is poor. If quality energy is ok
	then it uses it, scaled to about -10 so that in the early and middle stages of the search it will still jump
	out of it, but not in later stages
*/
double 
SearchEnergy::guidedPotentialQualityEnergy() const
{
	double cEn = contactEnergy();
	double pEn = potentialQualityEnergy(false);

	if (pEn > 0.0) return cEn;
	return pEn;
}

double
SearchEnergy::potentialQualityEnergy(bool verbose) const
{
	VirtualContact *contact;
	vec3 p,n,cn;

	int count = 0;
	//DBGP("Potential quality energy computation")
	for (int i=0; i<mHand->getGrasp()->getNumContacts(); i++) {

		contact = (VirtualContact*)mHand->getGrasp()->getContact(i);
		contact->computeWrenches(true, false);

		contact->getObjectDistanceAndNormal(mObject, &p, NULL);
		n= contact->getWorldNormal();

		double dist = p.len();
		p = normalise(p); //idiot programmer forgot to normalise
		double cosTheta = n % p;

		double factor = potentialQualityScalingFunction(dist, cosTheta);

		if (verbose) {
			fprintf(stderr,"VC %d on finger %d link %d\n",i,contact->getFingerNum(), contact->getLinkNum());
			fprintf(stderr,"Distance %f cosTheta %f\n",dist,cosTheta);
			fprintf(stderr,"Scaling factor %f\n\n",factor);
		}
		contact->scaleWrenches( factor );
		if (factor > 0.25) {
			count++;
			contact->mark(true);
		} else contact->mark(false);
	}

	double gq = -1 ,gv = -1;
	//to make computations more efficient, we only use a 3D approximation
	//of the 6D wrench space
	std::vector<int> forceDimensions(6,0);
	forceDimensions[0] = forceDimensions[1] = forceDimensions[2] = 1;
	if (count >= 3) {
		mHand->getGrasp()->updateWrenchSpaces(forceDimensions);
		gq = mEpsQual->evaluate();
		gv = mVolQual->evaluate();
	}
	if (verbose) {
		fprintf(stderr,"Quality: %f\n\n",gq);
	}
	if (count) {
		DBGP("Count: " << count << "; Gq: " << gq << "; Gv: " << gv);
	}
	return -gq;
}

/*! This function simply closes the hand and computes the real grasp quality that results
*/
int SearchEnergy::counter = 0;
#define FIRST_GOOD_TRIAL 201
double
SearchEnergy::autograspQualityEnergy() const
{
	DBGP("Autograsp quality computation");
	mHand->autoGrasp(false, 1.0);
	mHand->getGrasp()->collectContacts();
	mHand->getGrasp()->updateWrenchSpaces();
	double volQual = mVolQual->evaluate();
	double epsQual = mEpsQual->evaluate();
	if (epsQual < 0){
		epsQual = 0; //returns -1 for non-FC grasps
		volQual = 0;
	}
	/////////////////////insert here
	DBGP("Autograsp quality: " << volQual << " volume and " << epsQual << " epsilon.");
//	if(volQual > 0 && epsQual > 0)
//		DBGA("GOT ONE\n");
	return - (30 * volQual) - (100 * epsQual);
}

/*!	This version moves the palm in the direction of the object, attempting to establish contact on the palm
	before closing the fingers and establishing contacts on the finger.
*/
double
SearchEnergy::approachAutograspQualityEnergy() const
{
	transf initialTran = mHand->getTran();
	bool contact = mHand->approachToContact(30);
	if (contact) {
		if ( mHand->getPalm()->getNumContacts() == 0) contact = false;
	}
	if (!contact) {
		//if moving the hand in does not result in a palm contact, move out and grasp from the initial position
		//this allows us to obtain fingertip grasps if we want those
	  //		DBGA("Approach found no contacts");
		mHand->setTran( initialTran );
	} else {
	  //DBGA("Approach results in contact");
	}
	return autograspQualityEnergy();
}
//This version is similar to above, but it moves forward further and 
//it does NOT back off if no contact is found, it just attempts to grasp, blindly.
double SearchEnergy::approachToContactAutograspQualityEnergy() const
{
  //	transf initialTran = mHand->getTran();
  bool contact = mHand->approachToContact(100, false);
  
  if (!contact) {
    DBGP("Approach found no contacts");
    //		mHand->setTran( initialTran );
  } else {
    DBGP("Approach results in contact");
  }
  return autograspQualityEnergy();
}

void 
SearchEnergy::autoGraspStep(int numCols, bool &stopRequest) const
{
	//if no new contacts have been established, nothing new to compute
	stopRequest = false;
	if (!numCols) {
		return;
	}
	//if any of the kinematic chains is not balanced, early exit
	mHand->getWorld()->resetDynamicWrenches();
	//compute min forces to balance the system (pass it a "false")
	Matrix tau(mHand->staticJointTorques(false));
	int result = mHand->getGrasp()->computeQuasistaticForces(tau);
	if (result) {
		if (result > 0) {
			PRINT_STAT(mOut, "Unbalanced");
		} else {
			PRINT_STAT(mOut, "ERROR");
		}
		mCompUnbalanced = true;
		stopRequest = true;
		return;
	}
	assert(mObject->isDynamic());
	double* extWrench = static_cast<DynamicBody*>(mObject)->getExtWrenchAcc();
	vec3 force(extWrench[0], extWrench[1], extWrench[2]);
	if (force.len() > mMaxUnbalancedForce.len()) {
		mMaxUnbalancedForce = force;
	}
	//we could do an early exit here as well
}


double 
SearchEnergy::gfoEnergy() const
{
  
  bool contact = mHand->approachToContact(30);  
  transf initialTran = mHand->getTran();
  
  if (contact) {
    if ( mHand->getPalm()->getNumContacts() == 0) contact = false;
  }
  if (!contact) {
    //if moving the hand in does not result in a palm contact, move out and grasp from the initial position
    //this allows us to obtain fingertip grasps if we want those
    //		DBGA("Approach found no contacts");
    mHand->setTran( initialTran );
  } else {
  }
  
  mHand->autoGrasp(!mDisableRendering,1.0,false);
  //check if we have actually grasped the object
  if (mHand->getNumContacts(mObject) < 2) return 1.0e10;
  
  //Set dof forces to their max. It is not clear that this is the right approach here. 
  for (int d=0; d<mHand->getNumDOF(); d++) {
    mHand->getDOF(d)->setForce( mHand->getDOF(d)->getMaxForce() );
  }
  mHand->getWorld()->resetDynamicWrenches();
  //passing true means the set dof force will be used in computations
  Matrix tau(Matrix::ZEROES<Matrix>(mHand->getNumJoints(), 1));
  double objectiveValue;
  //retrieve task wrench -- currently stored as minimum wrench in grasp
  Matrix objWrench(Matrix::ZEROES<Matrix>(6,1));
  double taskWrench[6];
  mHand->getGrasp()->getTaskWrench(taskWrench);
  
  //Transform task wrench to hand coordinate system
  transf hti = mHand->getTran().inverse();
  vec3 force(taskWrench[0], taskWrench[1], taskWrench[2]);
  vec3 torque(taskWrench[3], taskWrench[4], taskWrench[5]);
  vec3 handForce = hti.rotation()*force;
  vec3 handTorque = hti.rotation()*(hti.translation()*force);
  handTorque += hti.rotation()*torque;
  taskWrench[0] = force[0];
  taskWrench[1] = force[1];
  taskWrench[2] = force[2];
  taskWrench[3] = torque[0];
  taskWrench[4] = torque[1];
  taskWrench[5] = torque[2];
  

  for(int i = 0; i < 6; ++i)
    objWrench.elem(i,0) = taskWrench[i];
  
  mHand->getGrasp()->collectContacts();
  mHand->getGrasp()->updateWrenchSpaces();
  double epsQual = mEpsQual->evaluate();
  if(epsQual <= 0)
   {
    DBGA("Epsilon < 0\n");
   return 1.0e10;
   }
  int optimizationSuccess = mHand->getGrasp()->computeQuasistaticForcesAndTorques(&tau, &objWrench, &objectiveValue);  
  if(optimizationSuccess)
    {
    DBGA("Optimization failed\n");
    return 1.0e10;
    }
  double* extWrench = static_cast<DynamicBody*>(mObject)->getExtWrenchAcc();


  //vec3 force(extWrench[0], extWrench[1], extWrench[2]);
  //vec3 torque(extWrench[3], extWrench[4], extWrench[5]);
  return -200.0 + objectiveValue;// + torque.len();
}

double SearchEnergy::contactGfoEnergy() const
{
  double testQualityThreshold = 20;
  double testQualityEnergy = contactEnergy();//guidedPotentialQualityEnergy();
  if (testQualityEnergy <  testQualityThreshold)
    return gfoEnergy()/1e8;
  else
    return testQualityEnergy;
}

double
SearchEnergy::compliantEnergy() const
{
	PROF_RESET(QS);
	PROF_TIMER_FUNC(QS);
	//approach the object until contact; go really far if needed
	mHand->findInitialContact(200);
	//check if we've actually touched the object
 	if (!mHand->getNumContacts(mObject)) return 1;

	//close the hand, but do additional processing when each new contact happens
	mCompUnbalanced = false; 
	mMaxUnbalancedForce.set(0.0,0.0,0.0);
	
	QObject::connect(mHand, SIGNAL(moveDOFStepTaken(int, bool&)), 
					 this, SLOT(autoGraspStep(int, bool&)));
	mHand->autoGrasp(!mDisableRendering, 1.0, false);
	QObject::disconnect(mHand, SIGNAL(moveDOFStepTaken(int, bool&)), 
				        this, SLOT(autoGraspStep(int, bool&)));

	if (mCompUnbalanced || mMaxUnbalancedForce.len() > unbalancedForceThreshold) {
		//the equivalent of an unstable grasp
	}

	//check if we've actually grasped the object
	if (mHand->getNumContacts(mObject) < 2) return 1;

	PRINT_STAT(mOut, "unbal: " << mMaxUnbalancedForce);

	//compute unbalanced force again. Is it zero?
	//but compute it for all the force that the dofs will apply
	//a big hack for now. It is questionable if the hand should even allow
	//this kind of intrusion into its dofs.
	for (int d=0; d<mHand->getNumDOF(); d++) {
		mHand->getDOF(d)->setForce( mHand->getDOF(d)->getMaxForce() );
	}
	mHand->getWorld()->resetDynamicWrenches();
	//passing true means the set dof force will be used in computations
	Matrix tau(mHand->staticJointTorques(true));
	int result = mHand->getGrasp()->computeQuasistaticForces(tau);
	if (result) {
		if (result > 0) {
			PRINT_STAT(mOut, "Final_unbalanced");
		} else {
			PRINT_STAT(mOut, "Final_ERROR");
		}
		return 1.0;
	} 
	double* extWrench = static_cast<DynamicBody*>(mObject)->getExtWrenchAcc();
	vec3 force(extWrench[0], extWrench[1], extWrench[2]);
	vec3 torque(extWrench[3], extWrench[4], extWrench[5]);

	//perform traditional f-c check
	mHand->getGrasp()->collectContacts();
	mHand->getGrasp()->updateWrenchSpaces();
	double epsQual = mEpsQual->evaluate();
	PRINT_STAT(mOut, "eps: " << epsQual);

	if ( epsQual < 0.05) return 1.0;

	PROF_PRINT(QS);
	PRINT_STAT(mOut, "torque: " << torque << " " << torque.len());
	PRINT_STAT(mOut, "force: " << force << " " << force.len());
	
	

	return -200.0 + force.len();// + torque.len();
}
void
SearchEnergy::dynamicsError(const char*) const
{
	DBGA("Dynamics error; early exit");
	mDynamicsError = true;
}

bool
SearchEnergy::contactSlip() const
{
	return mHand->contactSlip();
}

/*! Implements the following heuristic: for each chain, either the last link
	must have a contact, or the last joint must be maxed out. If this is true
	the dynamic autograsp *might* have been completed
*/
bool SearchEnergy::dynamicAutograspComplete() const
{
	return mHand->dynamicAutograspComplete();
}

double
SearchEnergy::dynamicAutograspEnergy() const
{
  DBGA("entered dynamic autograsp");
	//approach the object until contact; go really far if needed
        mHand->findInitialContact(200);
	//check if we've actually touched the object
	if (!mHand->getNumContacts(mObject)) return 1;

	//this is more of a hack to cause the hand to autograsp in dynamics way
	//the world's callback for dynamics should never get called as everything 
	//gets done from inside here
	mHand->getWorld()->resetDynamics();
	//I think this happens in each dynamics step anyway
	mHand->getWorld()->resetDynamicWrenches();
	mHand->getWorld()->turnOnDynamics();
	//this should set the desired values of the dof's
	//also close slowly, so we are closer to pseudo-static conditions
	mHand->autoGrasp(false, 0.5);

	QObject::connect(mHand->getWorld(), SIGNAL(dynamicsError(const char*)),
					 this, SLOT(dynamicsError(const char*)));
	//loop until dynamics is done
	mDynamicsError = false;
	int steps=0; int stepFailsafe = 1500;
	int autoGraspDone = 0; int afterSteps = 100;
	//first close fingers to contact with object
	while (1) {
		if (!(steps%100)) {DBGA("Step " << steps);}
		mHand->getWorld()->stepDynamics();
		if (mDynamicsError) break;
		//see if autograsp is done
		if (!autoGraspDone && dynamicAutograspComplete()) {
			autoGraspDone = steps;
		}
		//do some more steps after sutograsp
		if (autoGraspDone && steps - autoGraspDone > afterSteps) {
			break;
		}
		//and finally check stepfailsafe
		if (++steps > stepFailsafe) break;
	}

	if (mDynamicsError) {
		DBGA( "Dynamics error");
		return 2.0;
	} else if (steps > stepFailsafe) {
		DBGA( "Time failsafe");
		return 2.0;
	}
	DBGA("Autograsp done");

	//disable contacts on pedestal
	/*Body *obstacle;
	for (int b=0; b<mHand->getWorld()->getNumBodies(); b++) {
		Body *bod = mHand->getWorld()->getBody(b);
		if (bod->isDynamic()) continue;
		if (bod->getOwner() != bod) continue;
		obstacle = bod;
		break;
	}
	if (!obstacle) {
		PRINT_STAT(mOut, "Obstacle not found!");
		return 2.0;
		}
		mHand->getWorld()->toggleCollisions(false, obstacle);*/
	//and do some more steps
	steps = 0; afterSteps = 400;
	while (1) {
		if (!(steps%100)) {DBGA("After step " << steps);}
		mHand->getWorld()->stepDynamics();
		/*
		if (mHand->getDOF(0)->getForce() + 1.0e3 > mHand->getDOF(0)->getMaxForce()) {
			DBGA("Max force applied");
			break;
		}*/
		if (mDynamicsError) break;
		if (++steps > afterSteps) break;
	}
	//mHand->getWorld()->toggleCollisions(true, obstacle);
	QObject::disconnect(mHand->getWorld(), SIGNAL(dynamicsError(const char*)),
				    	this, SLOT(dynamicsError(const char*)));
	//turn off dynamics; world dynamics on shouldn't have done anything anyway
	mHand->getWorld()->turnOffDynamics();

	if (mDynamicsError) {
	  DBGA( "Dynamics error");
		return 2.0;
	}

	//if the object has been ejected output error
	if (mHand->getNumContacts(mObject) < 2) {
	  DBGA( "Ejected");
		return 0.0;
	}

	//perform traditional f-c check
	mHand->getGrasp()->collectContacts();
	mHand->getGrasp()->updateWrenchSpaces();
	double epsQual = mEpsQual->evaluate();
	DBGA( "eps: " << epsQual);

	if ( epsQual < 0.05) return -0.5;

	//grasp has finished in contact with the object
	DBGA( "Success 1");
	return -1.0;
}

/*! This version behaves like the autograsp energy, except it returns a huge penalty if the grasp has 0 hull
It is meant for searches that NEVER want to go where the grasp has no quality
*/
double
SearchEnergy::strictAutograspEnergy() const
{
//	double gq = autograspQualityEnergy();
	double gq = approachAutograspQualityEnergy();
	if (gq==0) return 1.0e8;
	else return gq;
}

double
SearchEnergy::numContactsEnergy() const
{
	transf initialTran = mHand->getTran();
	bool contact = mHand->approachToContact(30);
	if (contact) {
		if ( mHand->getPalm()->getNumContacts() == 0) contact = false;
	}
	if (!contact) {
		//if moving the hand in does not result in a palm contact, move out and grasp from the initial position
		//this allows us to obtain fingertip grasps if we want those
		DBGP("Approach found no contacts");
		mHand->setTran( initialTran );
	} else {
		DBGP("Approach results in contact");
	}
	return -0.1 * mHand->getNumContacts() - 3 * autograspQualityEnergy();
}
/* ---------------------------------- SCALING FUNCTIONS ---------------------------------- */
double
SearchEnergy::distanceFunction(double d) const
{
	double ERRORWIDTH=25;	// the function gets very close to 1 at about ERRORWIDTH * 4 mm from the object
	if (d > 0) {
		return ( 40.0 - 40.0 / pow(4.0,d/ERRORWIDTH) );
	} else {
		return -d;
	}
}

double 
SearchEnergy::potentialQualityScalingFunction(double dist, double cosTheta) const
{
	double sf = 0;
	/*
	(void*)&cosTheta;
	if (dist<0) return 0;
	sf += 100.0 / ( pow(2.0,dist/15.0) );
	//comment this out if you don't care about normals
	//sf += 100 - (1 - cosTheta) * 100.0 / 2.0;
	*/
/*
	if (cosTheta < 0.8) return 0; //about 35 degrees
	sf = 10.0 / ( pow((double)3.0,dist/25.0) ); 
	if (sf < 0.25) sf = 0; //cut down on computation for tiny values. more than 50mm away
	return sf;
*/
	/*
	if (cosTheta < 0.8) return 0; //about 35 degrees
	if (dist < 20) sf = 1;
	else {
		sf = 1.5 - 1.5 / ( pow((double)3.0,(dist-20)/25.0) );
		sf = cos( sf*sf ) + 1;
	}
	sf = sf*10;
	if (sf < 0.25) sf = 0; //cut down on computation for tiny values. more than 50mm away
	return sf;
	*/
	if (cosTheta < 0.7) return 0;
	if (dist > 50) return 0;
	sf = cos ( 3.14 * dist / 50.0) + 1;
	return sf;
}

double SearchEnergy::getEpsQual(){
  //mHand->getWorld()->findAllContacts();
  	mHand->getWorld()->updateGrasps();
	return mEpsQual->evaluate();
}

double SearchEnergy::getVolQual(){
  //mHand->getWorld()->findAllContacts();
  	mHand->getWorld()->updateGrasps();
	return mVolQual->evaluate();
}
//check whether the parentRobot can achieve the position specified in childState
bool SearchEnergy::analyzeAccessibility(Robot *parentRobot, GraspPlanningState *childState){

	std::vector<double> dofVals;
	dofVals.resize(parentRobot->getNumDOF());
	GraspPlanningState *tmp = new GraspPlanningState(childState);
	tmp->setPositionType(SPACE_COMPLETE,true);
	transf endTran;
	endTran.set(Quaternion(tmp->getPosition()->getVariable(3)->getValue(),
							tmp->getPosition()->getVariable(4)->getValue(),
							tmp->getPosition()->getVariable(5)->getValue(),
							tmp->getPosition()->getVariable(6)->getValue()),
				vec3(tmp->getPosition()->getVariable(0)->getValue(),
				tmp->getPosition()->getVariable(1)->getValue(),
				tmp->getPosition()->getVariable(2)->getValue()));
	if(parentRobot->invKinematics(endTran, &dofVals[0], 0) == SUCCESS){
		delete tmp;
		//parentRobot->forceDOFVals(&dofVals[0]);
		return true;
	}
	delete tmp;
	return false;
}
//---------------------------------- CLOSURE SEARCH ---------------------------------

void 
ClosureSearchEnergy::analyzeState(bool &isLegal, double &stateEnergy, const GraspPlanningState *state, bool noChange)
{
	//first we check if we are too close to any state in the avoid list
	if (mAvoidList) {
		std::list<GraspPlanningState*>::const_iterator it; int i=0;
		for (it = mAvoidList->begin(); it!=mAvoidList->end(); it++){
			if ( (*it)->distance(state) < mThreshold ) {
				isLegal = false;
				stateEnergy = 0.0;
				DBGP("State rejected; close to state " << i);
				return;
			}
			i++;
		}
	}

	//if not, we compute everything like we usually do
	SearchEnergy::analyzeState(isLegal, stateEnergy, state, noChange);
}
