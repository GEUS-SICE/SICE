// VERSION=3

function setup() {
  return {
    input: [  
      {
        datasource: "OLCI",
        bands: ["B01","B02","B03","B04","B05","B06","B07","B08","B09","B10","B11","B12","B13","B14","B15","B16","B17","B18","B19","B20","B21","SZA","VZA","SAA","VAA","TOTAL_COLUMN_OZONE"],                  
      }
    ],
    output: [
      {
        id: "toa1",
        bands: 1,
        sampleType: "FLOAT32",      
      },        
      {
        id: "toa2",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa3",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa4",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa5",
        bands: 1,
        sampleType: "FLOAT32",
      },
      {
        id: "toa6",
        bands: 1,
        sampleType: "FLOAT32",
      }, 
      {
        id: "toa7",
        bands: 1,
        sampleType: "FLOAT32",      
      },        
      {
        id: "toa8",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa9",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa10",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa11",
        bands: 1,
        sampleType: "FLOAT32",
      },
      {
        id: "toa12",
        bands: 1,
        sampleType: "FLOAT32",
      },
      {
        id: "toa13",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa14",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa15",
        bands: 1,
        sampleType: "FLOAT32",
      },
      {
        id: "toa16",
        bands: 1,
        sampleType: "FLOAT32",
      }, 
      {
        id: "toa17",
        bands: 1,
        sampleType: "FLOAT32",      
      },        
      {
        id: "toa18",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa19",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa20",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "toa21",
        bands: 1,
        sampleType: "FLOAT32",
      },        
      {
        id: "vza",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "sza",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "saa",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "vaa",
        bands: 1,
        sampleType: "FLOAT32",        
      },
      {
        id: "totalozone",
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

   
    
    
    let toa1_out = [];
    let toa2_out = [];
    let toa3_out = [];
    let toa4_out = [];
    let toa5_out = [];
    let toa6_out = [];
    let toa7_out = [];
    let toa8_out = [];
    let toa9_out = [];
    let toa10_out = [];
    let toa11_out = [];
    let toa12_out = [];
    let toa13_out = [];
    let toa14_out = [];
    let toa15_out = [];
    let toa16_out = [];
    let toa17_out = [];
    let toa18_out = [];
    let toa19_out = [];
    let toa20_out = [];
    let toa21_out = [];
    let sza_out = [];
    let vza_out = [];
    let saa_out = [];
    let vaa_out = [];
    let totalozone_out = [];
    let stop = 0;
    let sza_all = [];
    let sza_min = 0;
    
    
    for (var i=0; i < samples.length; i++){
        
        if (scenes.tiles[i].tileOriginalId.slice(43, 46) == "S3B") {
            sza_all.push(samples[i].SZA);
            
        }
    }
    
    
    sza_min = Math.min(...sza_all)
    
    for (var i=0; i < samples.length; i++){        
          
       if (stop == 0){ 
            if (scenes.tiles[i].tileOriginalId.slice(43, 46) == "S3B" && samples[i].SZA == sza_min) { 
            
                toa1_out.push(samples[i].B01);
                toa2_out.push(samples[i].B02);  
                toa3_out.push(samples[i].B03);
                toa4_out.push(samples[i].B04);
                toa5_out.push(samples[i].B05);
                toa6_out.push(samples[i].B06);
                toa7_out.push(samples[i].B07);
                toa8_out.push(samples[i].B08);
                toa9_out.push(samples[i].B09);
                toa10_out.push(samples[i].B10);
                toa11_out.push(samples[i].B11);
                toa12_out.push(samples[i].B12);
                toa13_out.push(samples[i].B13);
                toa14_out.push(samples[i].B14);
                toa15_out.push(samples[i].B15);
                toa16_out.push(samples[i].B16);
                toa17_out.push(samples[i].B17);
                toa18_out.push(samples[i].B18);
                toa19_out.push(samples[i].B19);
                toa20_out.push(samples[i].B20);
                toa21_out.push(samples[i].B21); 

                sza_out.push(samples[i].SZA);
                vza_out.push(samples[i].VZA);
                saa_out.push(samples[i].SAA);
                vaa_out.push(samples[i].VAA);
                totalozone_out.push(samples[i].TOTAL_COLUMN_OZONE);

                stop = 1
            }
         }
     }
  
    return {
      toa1 : toa1_out,
      toa2 : toa2_out,
      toa3 : toa3_out,
      toa4 : toa4_out,
      toa5 : toa5_out,
      toa6 : toa6_out,
      toa7 : toa7_out,
      toa8 : toa8_out,
      toa9 : toa9_out,
      toa10 : toa10_out,
      toa11 : toa11_out,
      toa12 : toa12_out,
      toa13 : toa13_out,
      toa14 : toa14_out,
      toa15 : toa15_out,
      toa16 : toa16_out,
      toa17 : toa17_out,
      toa18 : toa18_out,
      toa19 : toa19_out,
      toa20 : toa20_out,
      toa21 : toa21_out,
      saa : saa_out,
      vaa : vaa_out,
      sza : sza_out,
      vza : vza_out,
      totalozone : totalozone_out,
 
    };
}

function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = { "tiles":  scenes.tiles }
  }

