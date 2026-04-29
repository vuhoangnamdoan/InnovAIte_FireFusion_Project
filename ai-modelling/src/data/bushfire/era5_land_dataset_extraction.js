//-------------------------
// Global configuration
//-------------------------
var DATASET_ID = 'ECMWF/ERA5_LAND/HOURLY';
var START_DATE = ee.Date('2018-01-01');
var END_DATE = ee.Date('2023-01-01');
// End date is exclusive, so this covers from 01-01-2018 to 31-12-2022.
var EXPORT_START= ee.Date('2018-01-01');
var EXPORT_END = ee.Date('2018-02-01');
// Test export period first. Change this later for full montly/yearly exports. 
var INTERVAL_HOURS = 12;
var GRID_SCALE = 5000;
var EXPORT_NAME = 'FireFusion_ERA5Land_Victoria_12Hourly_5kmGrid';
var SELECTED_BANDS = [
  'temperature_2m',
  'skin_temperature',
  'soil_temperature_level_1',
  'surface_solar_radiation_downwards',
  'surface_thermal_radiation_downwards',
  'u_component_of_wind_10m',
  'v_component_of_wind_10m'
  ];

//-------------------------
// Dataset loader functions
//-------------------------

/**
Load Victoria boundary from FAO GAUL administrative boundary data.

Parameter: 
None

Returns: 
ee.FeatureCollection: Victoria state boundary.
*/
function loadVictoriaBoundary() {
  var australiaStates = ee.FeatureCollection('FAO/GAUL/2015/level1');

  return australiaStates
    .filter(ee.Filter.eq('ADM0_NAME', 'Australia'))
    .filter(ee.Filter.eq('ADM1_NAME', 'Victoria'));
}

/**
Load ERA5-Land hourly dataset from Google Earth Engine. 

Parameter: 
region(ee.FeatureCollection): Study area boundary.
startDate(ee.Date): Start date for dataset filtering.
endDate (ee.Date): Exclusive end date for dataset filtering.

Returns: 
ee.ImageCollection: ERA5-Land hourly data filtered by region, date, and selected bands.
*/

function loadEra5LandHourly(region,startDate, endDate) {
return ee.ImageCollection(DATASET_ID)
.filterDate(startDate, endDate)
.filterBounds(region)
.select(SELECTED_BANDS);
}

/**
Process selected ERA5_Land features
Temperature variables are converted from Kelvin to Celsius.
Radiation and wind variables are kept in original ERA5-Land units. 

Parameter: 
region(ee.Image): Raw ERA5-Land image.

Returns: 
ee.Image: Processed ERA5-Land image with model-ready feature names. 
*/

function processEra5Features(image) {
  var temperature2mC = image.select('temperature_2m')
  .subtract(273.15)
  .rename('temperature_2m_c');

  var skinTemperatureC = image.select('skin_temperature')
  .subtract(273.15)
  .rename('skin_temperature_c');

  var soilTemperatureLevel1C = image.select('soil_temperature_level_1')
  .subtract(273.15)
  .rename('soil_temperature_level_1_c');

  var radiationBands = image.select([
    'surface_solar_radiation_downwards',
    'surface_thermal_radiation_downwards'
    ]);

  var windBands = image.select([
    'u_component_of_wind_10m',
    'v_component_of_wind_10m'
    ]);

  return temperature2mC
  .addBands(skinTemperatureC)
  .addBands(soilTemperatureLevel1C)
  .addBands(radiationBands)
  .addBands(windBands)
  .copyProperties(image, ['system:time_start']);
}

/**
Aggregate hourly ERA5-Land data into 12-hour mean intervals.

Parameter: 
imageCollection (ee.ImageCollection): Processed hourly ERA5-Land collection.
startDate (ee.Date): Start date for aggregation.
endDate (ee.Date): Exclusive end date for aggregation. 
intervalHours (number): Aggregation interval in hours.
region(ee.FeatureCollection): Study area boundary.

Returns: 
ee.ImageCollection: 12 hour aggregated ERA5-Land collection. 
*/

function aggregateToTwelveHourly(imageCollection, startDate, endDate, intervalHours, region) {
  var totalHours = endDate.difference(startDate, 'hour');

  var timeSteps = ee.List.sequence(
    0, 
    totalHours.subtract(intervalHours),
    intervalHours
  );
  
  return ee.ImageCollection.fromImages(
    timeSteps.map(function(hourOffset) { 
      var intervalStart = startDate.advance(hourOffset, 'hour');
      var intervalEnd = intervalStart.advance(intervalHours, 'hour');
      var intervalCollection = imageCollection.filterDate(intervalStart, intervalEnd);
      var meanImage = intervalCollection.mean()
        .set('system:time_start', intervalStart.millis())
        .set('interval_start', intervalStart.format('YYYY-MM-dd HH:mm'))
        .set('interval_end', intervalEnd.format('YYYY-MM-dd HH:mm'));
      return meanImage.clip(region);
  })
);
}

/**
Create 5km x 5km grid cells across Victoria.

Parameter: 
region(ee.FeatureCollection): Study area boundary.
gridScale (number): Grid cell size in metres.

Returns: 
ee.FeatureCollection: Grid cells with grid_id values.  
*/

function createVictoriaGrid(region,gridScale) {
  var gridProjection = ee.Projection('EPSG:3857').atScale(gridScale); 
  var gridImage = ee.Image.random()
    .multiply(1000000)
    .toInt()
    .reproject(gridProjection);
  var grid = gridImage.reduceToVectors({
    geometry: region.geometry(),
    scale: gridScale,
    geometryType: 'polygon',
    reducer: ee.Reducer.countEvery(),
    maxPixels: 1e13
});

  return grid.map(function(feature){
    return feature.set('grid_id', feature.id());
  });
}

/**
Extract ERA5-Land feature values for each grid cell.

Parameter: 
imageCollection (ee.ImageCollection): 12-hour ERA5-Land collection.
grid (ee.FeatureCollection): 5 km grid cells.

Returns: 
ee.FeatureCollection: Flattened table of environmental features by grid cell and time.  
*/
function extractGridCellFeatures(imageCollection,grid){
  return imageCollection.map(function(image){
    var datetime = ee.Date(image.get('system:time_start'));
    var reducedGrid = image.reduceRegions({
      collection: grid,
      reducer: ee.Reducer.mean(),
      scale: 11132
    });

    return reducedGrid.map(function(feature){
      return feature
      .set('datetime', datetime.format('YYYY-MM-dd HH:mm'))
      .set('timestamp', datetime.millis())
      .set('interval_start', image.get('interval_start'))
      .set('interval_end', image.get('interval_end'))
    });
  }).flatten();
}

/**
Export dataset table to Google Drive.

Parameter: 
table(ee.FeatureCollection): Final extracted dataset.
exportName (string): Export task name and file prefix.

Returns: 
None. Creates an export task in Google Earth Engine. 
*/
function exportDatasetToDrive(table, exportName) {
  Export.table.toDrive({
    collection: table,
    description: exportName, 
    fileNamePrefix: exportName,
    fileFormat: 'CSV'
  });
}

/**
Main ERA5-Land dataset loader pipeline.

Parameter: 
None

Returns: 
None. Loads, processes, aggregates, extracts, and creates an export task. 
*/
    
function main() {
  print('Starting FireFusion ERA5-Land dataset loader...');
  var victoria = loadVictoriaBoundary();
  Map.centerObject(victoria,6);
  Map.addLayer(victoria, {}, 'Victoria Boundary');

  print('Loading ERA5-Land hourly dataset...');
  var era5Hourly = loadEra5LandHourly(
    victoria,
    START_DATE,
    END_DATE
  );
  
  print('Processing selected features...');
  var era5Processed = era5Hourly.map(processEra5Features);

  print('Aggregating hourly data into 12-hour intervals...');
  var era5TwelveHourly = aggregateToTwelveHourly(
    era5Processed,
    START_DATE,
    END_DATE,
    INTERVAL_HOURS,
    victoria
    );

  print('Creating 5km Victoria grid...');
  var victoriaGrid = createVictoriaGrid(
    victoria, 
    GRID_SCALE
    );
  Map.addLayer(victoriaGrid, {}, 'Victoria 5km Grid');

  print('Filtering export period...');
  var era5ExportCollection = era5TwelveHourly.filterDate(
    EXPORT_START, 
    EXPORT_END
    );

  print('Extracting ERA5-Land features by grid cell...');
  var extractedDataset = extractGridCellFeatures(
    era5ExportCollection,
    victoriaGrid
    );

  print('Creating Google Drive export task...');
  exportDatasetToDrive(
    extractedDataset,
    EXPORT_NAME
    );
  
  print('Dataset loader complete. Run the export task from the Tasks tab.');
}
main();
