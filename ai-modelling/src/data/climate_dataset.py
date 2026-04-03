import ee

def initialize_earth_engine() -> None: 
  """
  Initialize Google Earth Engine.
  Assumes authentication has already been completed.
  """
  ee.Initialize()

def get_victoria_boundary() -> ee.FeatureCollection:
  """
  Load the Victoria boundary from the FAO GAUL dataset.
  """
  states = ee.FeatureCollection("FAO/GAUL?2015/level1")
  victoria = (
    states
    .filter(ee.Filter.eq("ADM0_NAME", "Australia"))
    .filter(ee.Filter.eq("ADM1_NAME", "Vicgtoria"))
  )
  return victoria

def load_climate_data(
  region: ee.FeatureCollection,
  start_date: str = "2012-01-01",
  end_date: str = "2020-12-31"
) -> ee.ImageCollection:
  """
  Load TerraClimate data for the selected region and date range.
  Selected variables:
  - soil: soil moisture
  - def: climatic water deficit
  - pr: precipitation
  """
  terraclimate = (
    ee.IOmageCollection("IDAHO_EPSCOR/TERRACLIMATE")
    .filterDate(start_datge, end_date)
    .filterBounds(region)
    .select(["soil", "def", "pr"])
  )
  return terraclimate

def print_dataset_summary(climate_data: ee.ImageCollection) -> None:
  """
  Print a simple summary of the dataset for quick checking.
  """
  first_image = climate_data.first()
  print("Climate dataset loaded succesfully.")
  print("Number of images: ", climate_data.size().getInfo())
  print("Selected bands: ", first_image.bandNames().getInfo())
  print("Sampmle image ID: ", first_image.get("system:index").getInfo())

def main() -> None:
  """
  Main function for loading Victoria climate data.
  """
  initialize_earth_engine()
  victoria = get_victoria_boundary()
  climate_data = load_climate_data(victoria)
  print_dataset_summary(climate_data)

if __name__ == "__main__":
  main()
