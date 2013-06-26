/****************************************************************************
** ui.h extension file, included from the uic-generated form implementation.
**
** If you want to add, delete, or rename functions or slots, use
** Qt Designer to update this file, preserving your code.
**
** You should not define a constructor or destructor in this file.
** Instead, write your code in functions called init() and destroy().
** These will automatically be called by the form's constructor and
** destructor.
*****************************************************************************/

void GeometryLibDlg::setBody( Body *b )
{
 mBody = b;
 objectNameLabel->setText( "Object: " + mBody->getName() );
}

void GeometryLibDlg::fitPrimitivesButton_clicked()
{


 #define DatasetType geometry::Mesh<>

 std::vector<geometry::IntegrableTriangle<>*> triangles;
 SoGeometryToTriangleList(mBody->getIVGeomRoot(), &triangles);
 fprintf(stderr,"So to triangles conversion done.\n");

// mBody->getIVGeomRoot()->removeAllChildren();

 geometry::Mesh<> mesh;
 mesh.insert(triangles.begin(), triangles.end());
 geometry::PointCloud<> point_cloud = mesh.GetVertices();  


 float tolerance = .04f;

 // setup single fitter
 primitives::SuperquadricCost<> cost_function;
 fitter::ThreadedResidualizer<> residualizer;  
 fitter::LevmarFitter<> lmf;
 lmf.SetUseCentralDifferences(false); 
 lmf.SetMaxIterations(100);         
 lmf.SetErrorTolerance(tolerance * .001 * mesh.BallSize());
 lmf.SetNumericalJacobianDelta(.1f);
 
 // setup callback
 class Callback : public fitter::MultiplePrimitiveUpdateCallback<primitives::Superquadric<>, DatasetType> {
   Body& mBody_;
  public:
   Callback(Body& body) : mBody_(body) { }


   virtual void UpdateEvent(std::list<const fitter::PrimitiveAndData<primitives::Superquadric<>, DatasetType>*>& primitives) const {
     std::vector<geometry::IntegrableTriangle<>*> output_vec;
     std::list<const primitives::Primitive<>*> primitives_list;



     for (std::list<const fitter::PrimitiveAndData<primitives::Superquadric<>, DatasetType >*>::iterator pandd = primitives.begin();
         pandd != primitives.end(); ++pandd) {
       //for (DatasetType::const_iterator it = (*pandd)->data_.begin(); it != (*pandd)->data_.end(); ++it) {
       //  output_vec.push_back(*it);
       //}
       primitives_list.push_back(&((*pandd)->primitive_));
     }
     primitivesToTriangleList(&output_vec, &primitives_list);
     SoGroup *root = new SoGroup();
     triangleListToSoGeometry(root, &output_vec);

     mBody_.getIVPrimitiveRoot()->removeAllChildren();
     mBody_.getIVPrimitiveRoot()->addChild(root);
	 QMessageBox::warning(NULL,"GraspIt!","Fitter update!",QMessageBox::Ok, Qt::NoButton,Qt::NoButton);
   }
 } callback(*mBody);

 // setup multiple fitter
 fitter::SplitMergeFitter<primitives::Superquadric<>, DatasetType> smf;
 smf.SetSplitTolerance(tolerance * mesh.BallSize());
 smf.SetMergeTolerance(tolerance * mesh.BallSize());

 cerr << "Split tolerance: " << (tolerance * mesh.BallSize()) << "\n";
 cerr << "Merge tolerance: " << (tolerance * mesh.BallSize()) << "\n";

 //smf.SetUpdateCallback(callback);


  
 // fit   

 // change to point_cloud if needed
 std::list<const fitter::PrimitiveAndData<primitives::Superquadric<>, DatasetType>*>& primitives = 
      smf.Fit(mesh, lmf, cost_function, residualizer);

 std::vector<geometry::IntegrableTriangle<>*> output_vec;
 std::list<const primitives::Primitive<>*> primitives_list;
 for (std::list<const fitter::PrimitiveAndData<primitives::Superquadric<>, DatasetType>*>::iterator pandd = primitives.begin();
     pandd != primitives.end(); ++pandd) {
   //for (DatasetType::const_iterator it = (*pandd)->data_.begin(); it != (*pandd)->data_.end(); ++it) {
   //  output_vec.push_back(*it);
   //}
   primitives_list.push_back(&((*pandd)->primitive_));
 }
 primitivesToTriangleList(&output_vec, &primitives_list);

 SoGroup *root = new SoGroup();
 triangleListToSoGeometry(root, &output_vec);
 fprintf(stderr,"Triangles conversion back to geometry done.\n");

 mBody->getIVPrimitiveRoot()->removeAllChildren();
 mBody->getIVPrimitiveRoot()->addChild(root);
}

void GeometryLibDlg::exitButton_clicked()
{
	QDialog::accept();
}
