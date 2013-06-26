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
// $Id: graspRecord.cpp,v 1.3 2009/04/21 14:53:08 cmatei Exp $
//
//######################################################################

#include "graspRecord.h"
#include "gloveInterface.h"

GraspRecord::GraspRecord(int size)
{
	mSize = size;
	mPose = new CalibrationPose(mSize);

	mTran = transf::IDENTITY;
	mObjectName = mRobotName = QString("not_set");
}

GraspRecord::~GraspRecord()
{
	delete mPose;
}

void GraspRecord::writeToFile(FILE *fp)
{
	//write names
	fprintf(fp,"%s\n",mObjectName.latin1());
	fprintf(fp,"%s\n",mRobotName.latin1());
	//write transform
	Quaternion q = mTran.rotation();
	fprintf(fp,"%f %f %f %f ",q.x, q.y, q.z, q.w);
	vec3 t = mTran.translation();
	fprintf(fp,"%f %f %f\n",t.x(), t.y(), t.z());
	//write pose
	mPose->writeToFile(fp);
}

void GraspRecord::readFromFile(FILE *fp)
{
	float x,y,z,w;
	//read names
	char name[1000];
	do {
		fgets(name, 1000, fp);
	} while (name[0]=='\n' || name[0]=='\0' || name[0]==' ');
	mObjectName = QString(name);
	mObjectName = mObjectName.stripWhiteSpace();
	fprintf(stderr,"object: %s__\n",mObjectName.latin1());
	do {
		fgets(name, 1000, fp);
	} while (name[0]=='\n' || name[0]=='\0' || name[0]==' ');
	mRobotName = QString(name);
	mRobotName = mRobotName.stripWhiteSpace();
	fprintf(stderr,"robot: %s__\n",mRobotName.latin1());
	//read transform
	fscanf(fp,"%f %f %f %f",&x, &y, &z, &w);
	Quaternion q(w, x, y, z);
	fscanf(fp,"%f %f %f",&x, &y, &z);
	vec3 t(x,y,z);
	mTran.set(q,t);
	//read pose
	mPose->readFromFile(fp);
	mSize = mPose->getSize();
}

void loadGraspListFromFile(std::vector<GraspRecord*> *list, const char *filename)
{
	FILE *fp = fopen(filename, "r");
	if (fp==NULL) {
		fprintf(stderr,"Unable to open file %s for reading\n",filename);
		return;
	}

	GraspRecord *newGrasp;
	int nGrasps;
	fscanf(fp,"%d",&nGrasps);
	for(int i=0; i<nGrasps; i++) {
		newGrasp = new GraspRecord(0);
		newGrasp->readFromFile(fp);
		list->push_back(newGrasp);
	}

	fclose(fp);
}

void writeGraspListToFile (std::vector<GraspRecord*> *list, const char *filename)
{
	FILE *fp = fopen(filename, "w");
	if (fp==NULL) {
		fprintf(stderr,"Unable to open file %s for reading\n",filename);
		return;
	}

	fprintf(fp,"%d\n",(int)list->size());
	for (int i=0; i<(int)list->size(); i++) {
		(*list)[i]->writeToFile(fp);
	}

	fclose(fp);
}
