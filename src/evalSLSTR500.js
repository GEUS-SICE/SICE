// VERSION=3

function setup() {
  return {
    input: [  
        {
        datasource: "OLCI",
        bands: ["SZA"],                  
      },
      {
        datasource: "SLSTR",
        bands: ["S1","S5"],                  
      }
    ],
    output: [
      {
        id: "pixelidSLSTR500",
        bands: 1,
        sampleType: "FLOAT32",      
      },  
      {
        id: "S5",
        bands: 1,
        sampleType: "FLOAT32",      
      }, 
       {
        id: "S1",
        bands: 1,
        sampleType: "FLOAT32",      
      }
    ],
    mosaicking: "TILE",
  };
}

// function updateOutput(outputs, collections) {
//  Object.values(outputs).forEach((output) => {
//    output.bands = collections.scenes.length;
//  });
// }

// Set constants as global variables which can be used in all functions

function evaluatePixel(samples, scenes, inputMetadata, customData, outputMetadata) {
    
    
    let S1_out = [];
    let S5_out = [];
    let sza_all = 180;
    let time_idx = 0;
    let pixelid_out = [];
    let idx = 0;
    let time_slstr = 0;
  
   for (var i=0; i < scenes.OLCI.scenes.length; i++){
        if (scenes.OLCI.scenes[i].tileOriginalId.includes("S3A")) {
            if (samples.OLCI[i].SZA < sza_all) {
                time_idx = scenes.OLCI.scenes[i].tileOriginalId.slice(71, 75)
                sza_all = samples.OLCI[i].SZA
            }
        }
    }
    
    for (var i=0; i < scenes.SLSTR.scenes.length; i++){
        
        if (scenes.SLSTR.scenes[i].tileOriginalId.includes("S3A")) {
           time_slstr = scenes.SLSTR.scenes[i].tileOriginalId.slice(72, 76)
            
            if (parseInt(time_idx) == parseInt(time_slstr)) {
                
                idx = scenes.SLSTR.scenes[i].__idx
              
            }
        }
    }
    
    pixelid_out.push(idx);
    S1_out.push(samples.SLSTR[idx].S1);
    S5_out.push(samples.SLSTR[idx].S5);
    
    return {
      pixelidSLSTR500 : pixelid_out,  
      S1 : S1_out,
      S5 : S5_out,
    };
  }


function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = { "tiles":  scenes }
    
  }

