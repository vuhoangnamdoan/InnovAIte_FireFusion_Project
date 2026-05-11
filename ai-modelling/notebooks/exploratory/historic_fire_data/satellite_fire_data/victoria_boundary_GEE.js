// Victoria Boundary Exporter
// Extracts FAO/GAUL/2015 Victoria boundary
// To use, copy into GEE script interface, run from tasks, donwload from Google Drive

// Load Victoria boundary from FAO/GAUL 2015
function loadVictoriaBoundary() {
  var australiaStates = ee.FeatureCollection('FAO/GAUL/2015/level1');

  return australiaStates
    .filter(ee.Filter.eq('ADM0_NAME', 'Australia'))
    .filter(ee.Filter.eq('ADM1_NAME', 'Victoria'));
}

function main() {
  print('Loading Victoria boundary from FAO/GAUL/2015...');
  
  var victoria = loadVictoriaBoundary();
  
  // Print boundary info
  print('Victoria boundary loaded');
  print('Bounds:', victoria.geometry().bounds().getInfo());
  
  // Visualize on map
  Map.centerObject(victoria, 6);
  Map.addLayer(victoria, {color: 'FF0000'}, 'Victoria Boundary');
  
  // Export to Google Drive as GeoJSON
  Export.table.toDrive({
    collection: victoria,
    description: 'Victoria_FAO_GAUL_2015',
    fileNamePrefix: 'victoria_boundary_fao_gaul_2015',
    fileFormat: 'GeoJSON'
  });
  
  print('Export task created. Check Tasks tab to run.');
}

main();