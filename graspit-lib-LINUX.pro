# Linux-specific libraries for GraspIt!. Included from graspit.pro - not for standalone use.
qt += opengl
makestatic{
LIBS +=  -L/home/jweisz/qt/qt4-x11-4.5.3really4.5.2/lib/ -L/lib/ -L/usr/lib -L/usr/local/gfortran/lib/ -Wl,-Bdynamic,-lGL,-lgfortran,-lz,-lgthread-2.0,-lgtk-x11-2.0,-lSM,-lfontconfig,-lgcc_s -Wl,-Bstatic
}


# ---------------------- Blas and Lapack ----------------------------------

LIBS += -lblas -llapack 

HEADERS += include/lapack_wrappers.h


# ---------------------- General libraries and utilities ----------------------------------

LIBS	+= qhull/libqhull.a -L$(COINDIR)/lib -lSoQt -lCoin 
MOC_DIR = .moc
OBJECTS_DIR = .obj


#------------------------------------ add-ons --------------------------------------------

mosek {
	INCLUDEPATH += $(MOSEK6_0_INSTALLDIR)/tools/platform/linux32x86/h/
        LIBS += -L$(MOSEK6_0_INSTALLDIR)/tools/platform/linux32x86/bin/ -lmosek -liomp5
}

cgal_qp {
	error("CGAL linking only tested under Windows")
}

boost {
	error("Boost linking only tested under Windows")
}

hardwarelib {
	error("Hardware library only available under Windows")
}
