// VERSION=3

function setup() {
  return {
    input: [  
      {
        datasource: "COP_30",
        bands: ["DEM"],
      }
    ],
    output: [

      {
        id: "dem",
        bands: 1,
        sampleType: "FLOAT32",
      }  
    ],
    mosaicking: "SIMPLE",
  };
}

// function updateOutput(outputs, collections) {
//  Object.values(outputs).forEach((output) => {
//    output.bands = collections.scenes.length;
//  });
// }

// Set constants as global variables which can be used in all functions

function evaluatePixel(samples) {
    
    let dem = [];
    
    
    dem.push(samples.DEM) 
    
    return {
      dem : dem 
    };
  }

