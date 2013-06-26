#include "ContactPDModels.h"
#include <math.h>
#include "debug.h"
#include "matvec3D.h"
//FIXME:Not all math.h contain a defition for pi, and the use
//of it elsewhere in graspit may not be portable!  This problem should
//be examined more thoroughly and resolved in a consistent manner
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

ContactPressureDistributionModels::ContactPressureDistributionModels(){
	mtype = HERTZIAN;
}

double ContactPressureDistributionModels::maxFrictionOverTotalLoad(double * params){
	switch(mtype) {
		case WINKLER:{
			double a = params[0],b = params[1];
			return 8/15*sqrt(a*b);
			}
		case HERTZIAN:{
			double a = params[0],b = params[1];
			return 3*M_PI/16*sqrt(a*b);
			}
	}
	DBGA("ContactPressureDistributionModels::Unknown contact pressure distribution type");
	return -1;
}

double ContactPressureDistributionModels::pressureDistribution(double * params, double x, double y){
switch(mtype){
		case WINKLER:{
			double a = params[0],b = params[1], K = params[2], h = params[3], delta = params[4];
			return K*delta/h*(1-pow(x,2)/pow(a,2) - pow(y,2)/pow(b,2));
			}
		case HERTZIAN:{
			double a = params[0],b = params[1];
			return 3*M_PI/16*sqrt(a*b);
			}
	}
DBGA("ContactPressureDistributionModels::Unknown contact pressure distribution type");
return -1;
}

/*FIXME: Lame implementation - there are faster ways*/
void ContactPressureDistributionModels::distributionSamples(double a, double b, int majRows, int minRows, std::vector<position> &pVec )
{
	for (int inda = 0; inda < majRows; inda ++){
		for (int indb = 0; indb < minRows; indb ++){	
			double majCoord = -.5*a+ (inda+.5)*a/majRows; //(inda/(2*majRows) - 1 + .5/majRows)*a;
			double minCoord = -.5*b+ (indb+.5)*b/minRows;//(indb/(2*minRows) - 1 + .5/minRows)*b;
			if((pow(majCoord/(a/2),2) + pow(minCoord/(b/2),2)) <= 1)
				pVec.push_back(position(majCoord, minCoord, 0));
		}
	}
}

/*FIXME: logical constness is wanted for pVec
*/
void ContactPressureDistributionModels::sampleForces(double * params, double a, double b, int majRows, int minRows, const std::vector<position> &pVec, std::vector<double> &forceVec ){
	double sampleArea = a/majRows * b/minRows;
	for(unsigned int pind = 0; pind < pVec.size(); pind++){
		forceVec.push_back(sampleArea * pressureDistribution(params, pVec[pind].x(),pVec[pind].y()));
	}
}
