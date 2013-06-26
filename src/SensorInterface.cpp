#include <Inventor/nodes/SoCone.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoCylinder.h>
#include <Inventor/nodes/SoIndexedFaceSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoTransform.h>
#include <Inventor/nodes/SoTranslation.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoSphere.h>


#include "body.h"
#include "world.h"
#include "SensorInterface.h"
#include "matvec3D.h"
#include "qstring.h"
#include "qstringlist.h"

void BodySensor::init(Link * body){
	sbody = static_cast<SensorLink*>(body);
	myOutput.stype = BODY;
	myOutput.sensorReading = new double[6];
	memset(myOutput.sensorReading, 0, 6*sizeof(double));
	sbody->setBodySensor(this);
	sbody->getWorld()->addSensor(this);
}

BodySensor :: BodySensor(Link * body){
	BodySensor::init(body);
}
BodySensor::BodySensor(const BodySensor & fs, Link * sl)
	{
		BodySensor::init(sl);	
		last_world_time = 0;
		groupNumber = fs.groupNumber;
	}
bool
BodySensor :: updateSensorModel(){
sensorModel();
return true;
}

//FIXME this should be more flexible.
double
BodySensor::getTimeStep(){
	return .0025;
	/*static double lastTime = 0;
	double currTime, stepSize;
	World * sbworld = sbody->getWorld();
	currTime = sbworld->getWorldTime();
	stepSize = currTime - lastTime;
	lastTime =  currTime;
	return stepSize;*/
}
double BodySensor::retention_level = .1;

//simple model lowpass filters all forces.


//Temporary function for adding these vectors.  A faster way may be necessary
void inline 
addVector6(double * force, double * contactForce){
	for(int ind = 0; ind < 6; ind ++)
		force[ind]+=contactForce[ind];
}

void
BodySensor::sensorModel(){
	double forces[6] = {0,0,0,0,0,0};
	std::list<Contact *>::const_iterator cp;
	std::list<Contact *> cList = sbody->getContacts();
	//Adding contacts

	for(cp = cList.begin(); cp != cList.end(); cp++){
		double * contactForce; 
		if(sbody->getWorld()->dynamicsAreOn())
			contactForce = (*cp)->getDynamicContactWrench();
		else{
			double tempForce[6] = {0, 0, 1, 0, 0, 0};
			contactForce = tempForce;
		}
		addVector6(forces, contactForce);
	}
	//std::cout << "Body Sensor Reading: ";
	//Adding Forces
	double ts = getTimeStep();
	if (ts > 0.0)
		for(int ind = 0; ind < 6; ind++){
			myOutput.sensorReading[ind] = forces[ind] * (retention_level) + myOutput.sensorReading[ind] * (1.0-retention_level);
		//	std::cout << myOutput.sensorReading[ind] << " ";
		}
		//std::cout<<std::endl;
	sbody->setEmColor(myOutput.sensorReading[2]/3.0,0,1);
}


void
BodySensor::resetSensor(){
	for(int ind =0; ind < 6; ind ++)
		myOutput.sensorReading[ind] = 0;
}

SoSeparator * 
BodySensor::getVisualIndicator(){
	return NULL;
};

bool BodySensor::setGroupNumber(int gn){
	groupNumber = gn;
	return true;
}
/*bool RegionFilteredSensor::projectSensorToBody(){
	std::vector <position> vertices;
	sbody->getGeometryVertices(&vertices);
	
}
*/
void BodySensor::outputSensorReadings(QTextStream & qts){
	SensorOutput * so = Poll();
	int sNum = SensorOutputTools::getSensorReadingNumber(so);
	qts << "Body "; 
	for(int sInd = 0; sInd < sNum; sInd ++){
		qts << " ";	
		qts << so->sensorReading[sInd];
	}
	qts << endl;
}

bool
RegionFilteredSensor::filterContact(Contact * cp){
	position ps = cp->getPosition();
	return filterContact(pos[0], pos[1], ps);
}

bool
RegionFilteredSensor::filterContact(const position & boundaryPos0, const position & boundaryPos1, const position & ps){
	double p0x = boundaryPos0.x();
	double p0y = boundaryPos0.y();
	double p0z = boundaryPos0.z();
	double p1x = boundaryPos1.x();
	double p1y = boundaryPos1.y();
	double p1z = boundaryPos1.z();

	if((p0x <= ps[0] && p0y <= ps[1] && p0z <= ps[2]) &&
		(p1x >= ps.x() && p1y >= ps.y() && p1z >= ps.z())){
		return true;
	}
	return false;
}



bool
RegionFilteredSensor::setFilterParams(QString * params){
	QStringList qsl = params->split(",");
	pos[0][0]= qsl[0].toFloat();
	pos[0][1]= qsl[1].toFloat();
	pos[0][2]= qsl[2].toFloat();
	pos[1][0]= qsl[3].toFloat();
	pos[1][1]= qsl[4].toFloat();
	pos[1][2]= qsl[5].toFloat();
	return setFilterParams(pos);
}

bool RegionFilteredSensor::setFilterParams(position pos[]){
	int32_t cIndex[30];
	sbv[0].setValue(pos[0][0],pos[0][1],pos[0][2]);
	sbv[1].setValue(pos[0][0],pos[1][1],pos[0][2]);
	sbv[2].setValue(pos[0][0],pos[1][1],pos[1][2]);
	sbv[3].setValue(pos[0][0],pos[0][1],pos[1][2]);
	sbv[4].setValue(pos[1][0],pos[0][1],pos[0][2]);
	sbv[5].setValue(pos[1][0],pos[1][1],pos[0][2]);
	sbv[6].setValue(pos[1][0],pos[1][1],pos[1][2]);
	sbv[7].setValue(pos[1][0],pos[0][1],pos[1][2]);
	//face 1
	cIndex[0] = 0;
	cIndex[1] = 1;
	cIndex[2] = 2;
	cIndex[3] = 3;
	cIndex[4] = -1;
	//face 2
	cIndex[5] = 0;
	cIndex[6] = 1;
	cIndex[7] = 5;
	cIndex[8] = 4;
	cIndex[9] = -1;
	//face 3
	cIndex[10] = 0;
	cIndex[11] = 3;
	cIndex[12] = 7;
	cIndex[13] = 4;
	cIndex[14] = -1;
	//face 4
	cIndex[15] = 2;
	cIndex[16] = 6;
	cIndex[17] = 7;
	cIndex[18] = 3;
	cIndex[19] = -1;
	//face 5
	cIndex[20] = 1;
	cIndex[21] = 2;
	cIndex[22] = 6;
	cIndex[23] = 5;
	cIndex[24] = -1;
	//face 6
	cIndex[25] = 4;
	cIndex[26] = 5;
	cIndex[27] = 6;
	cIndex[28] = 7;
	cIndex[29] = -1;
	ifs->coordIndex.setValues(0,30,cIndex);

	coords->point.setValues(0,8,sbv);
	visualIndicator->addChild(coords);
	sbody->getIVRoot()->addChild(visualIndicator);
	visualIndicator->addChild(IVMat);
	visualIndicator->addChild(ifs);
	IVMat->emissiveColor.setValue(1.0,1.0,1.0);
	return true;
}

void
RegionFilteredSensor::sensorModel(){
	double forces[6] = {0,0,0,0,0,0};
	std::list<Contact *>::const_iterator cp;
	std::list<Contact *> cList = sbody->getContacts();
	//Adding contacts
	if(sbody->getWorld()->dynamicsAreOn()){
	for(cp = cList.begin(); cp != cList.end(); cp++){
		double * contactForce = (*cp)->getDynamicContactWrench();
		//std::cout << "Contact pos:" << (*cp)->getPosition()[0] <<" " <<(*cp)->getPosition()[1] <<" "<< (*cp)->getPosition()[2] << std::endl;

		if (filterContact(*cp))
			addVector6(forces, contactForce);
	}
	//Adding Forces
	double ts = getTimeStep();
	if (ts > 0.0)
		for(int ind = 0; ind < 6; ind++){
			myOutput.sensorReading[ind] = forces[ind] * (retention_level) + myOutput.sensorReading[ind] * (1.0-retention_level);
			//std::cout << myOutput.sensorReading[ind] << " ";
		}
	}
	else{
		myOutput.sensorReading[2] = 0;
		for(cp = cList.begin(); cp != cList.end(); cp++){
			if(sbody->getWorld()->softContactsAreOn() && ((*cp)->getBody1()->isElastic() || (*cp)->getBody2()->isElastic())){
				std::vector<position> pVec;
				std::vector<double> forceVec;
				(*cp)->getStaticContactInfo(pVec, forceVec);
				//transform the boundary positions OUT of body coordinates to contact coordinates
				//this results in fewer expensive matrix operations
				//fixme test that this is correct
				transf contact = (*cp)->getContactFrame();//.inverse();
				/*For the sake of argument, lets say we take the position of the contact on the body, 
				and look at how that works
				*/
				mat3 contactRot = (*cp)->getRot();
				for (unsigned int pInd = 0; pInd < pVec.size(); pInd ++){
					//it appears that the contact frame is a roto-inversion
					if(filterContact(pos[0],pos[1], (contactRot*(1000*pVec[pInd]))*contact))
						myOutput.sensorReading[2]+= forceVec[pInd]* 10000000;
				}

			}
			else if (filterContact(*cp)){
				myOutput.sensorReading[2] += 1;
			}
		}
	}
	IVMat->emissiveColor.setValue(1.0-myOutput.sensorReading[2]/3,1.0,1.0-myOutput.sensorReading[2]/3);
	//std::cout<<std::endl;
}


void RegionFilteredSensor::init(){
coords = new SoCoordinate3;
ifs = new SoIndexedFaceSet;
visualIndicator = new SoSeparator;
IVMat = new SoMaterial;
IVMat->diffuseColor.setIgnored(true);
IVMat->ambientColor.setIgnored(true);
IVMat->specularColor.setIgnored(true);
IVMat->emissiveColor.setIgnored(false);
IVMat->shininess.setIgnored(true);
}

RegionFilteredSensor::RegionFilteredSensor(Link * body) : BodySensor(body){
	RegionFilteredSensor::init();
return;
}

RegionFilteredSensor::RegionFilteredSensor(const RegionFilteredSensor & fs, Link * sl):BodySensor(sl)
{
	RegionFilteredSensor::init();
	last_world_time = 0;
	groupNumber = fs.groupNumber;
	pos[0] = fs.pos[0];
	pos[1] = fs.pos[1];
	setFilterParams(pos);

}


SoSeparator * 
RegionFilteredSensor::getVisualIndicator(){
	
	return visualIndicator;
};

void RegionFilteredSensor::outputSensorReadings(QTextStream & qts){
	SensorOutput * so = Poll();
	int sNum = SensorOutputTools::getSensorReadingNumber(so);
	qts << "Filtered "; 
	qts << pos[0][0] << " " << pos[0][1] << " " << pos[0][2] << " " << pos[1][0] << " " << pos[1][1] << " " << pos[1][2];
	for(int sInd = 0; sInd < sNum; sInd ++){
		qts << " ";	
		qts << so->sensorReading[sInd];
	}
	qts << endl;
}

BodySensor * RegionFilteredSensor::clone(SensorLink * sl)
{
	return new RegionFilteredSensor(*this, static_cast<Link *>(sl));
}

RegionFilteredSensor::~RegionFilteredSensor(){
	visualIndicator->removeAllChildren();
	sbody->getIVRoot()->removeChild(visualIndicator);
}

int SensorOutputTools::getSensorReadingNumber(SensorOutput * so){
	switch (so->stype){
		case BODY: //fall through
		case TBODY:
			return 6;
	}
	return -1;
}