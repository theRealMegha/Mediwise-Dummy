import pytesseract
import re
import pandas as pd
import joblib
import numpy as np
import os
import sys
import shutil
import logging
from pathlib import Path
from PIL import Image

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. SET TESSERACT PATH (Robust Configuration)
def setup_tesseract():
    """Attempt to find Tesseract executable in common locations."""
    # Check env var
    tess_env = os.environ.get('TESSERACT_CMD')
    if tess_env and os.path.exists(tess_env):
        pytesseract.pytesseract.tesseract_cmd = tess_env
        logger.info(f"Using Tesseract from environment variable: {tess_env}")
        return

    # Check common Windows paths
    common_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'D:\Program Files\Tesseract-OCR\tesseract.exe', # Check D drive too just in case
        os.path.join(os.getenv('LOCALAPPDATA', ''), 'Tesseract-OCR', 'tesseract.exe')
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Using Tesseract from found path: {path}")
            return

    # Fallback to PATH
    if shutil.which('tesseract'):
        logger.info("Using Tesseract from system PATH")
        return

    logger.warning("Tesseract not found in common locations. OCR may fail if not in PATH.")

setup_tesseract()

# 2. PRE-LOAD MODELS (Global scope so they load once when server starts)
BASE_PATH = Path(__file__).resolve().parent
MODEL = None
LE = None
RECS_DF = None
MODEL_COLUMNS = [
    "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC", 
    "PLT", "NEUT%", "LYMPH%", "RDW", "RETIC%", "EOS%", 
    "BASO%", "PLT_mean_volume"
]

def load_ml_assets():
    global MODEL, LE, RECS_DF
    try:
        model_path = BASE_PATH / 'medical_model.pkl'
        le_path = BASE_PATH / 'label_encoder.pkl'
        recs_path = BASE_PATH / 'cbc_disease_recommendations.csv'

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}")
        if not le_path.exists():
            raise FileNotFoundError(f"Label encoder not found at {le_path}")
        if not recs_path.exists():
            raise FileNotFoundError(f"Recommendations CSV not found at {recs_path}")

        MODEL = joblib.load(model_path)
        LE = joblib.load(le_path)
        RECS_DF = pd.read_csv(recs_path)
        logger.info("ML Assets loaded successfully.")
    except Exception as e:
        logger.critical(f"Critical Error Loading ML Assets: {e}")
        MODEL = None # Ensure explicit None if failed

load_ml_assets()

def run_medical_assistant(report_filename):
    logger.info(f"Starting medical assistant analysis for: {report_filename}")
    
    if MODEL is None:
        logger.error("ML Models are not loaded. Cannot predict.")
        return {"error": "Internal Server Error: ML Models not available."}

    try:
        # --- FAST EXTRACTION ---
        try:
            img = Image.open(report_filename)
            logger.info("Image opened successfully.")
            full_text = pytesseract.image_to_string(img, config='--psm 6')
            logger.info(f"OCR finished. Extracted {len(full_text)} characters.")
        except Exception as e:
            logger.error(f"OCR Failed: {e}")
            return {"error": f"OCR Failed: {str(e)}"}
        
        extracted_data = {}
        for m in MODEL_COLUMNS:
            # Flexible regex to find metric + number
            search_term = re.escape(m).replace(r'\_', r'.*?') 
            pattern = rf"{search_term}.*?(\d+\.?\d*)"
            match = re.search(pattern, full_text, re.IGNORECASE)
            
            value = float(match.group(1)) if match else 0.0
            extracted_data[m] = value
            if match:
                 logger.debug(f"Extracted {m}: {value}")
            else:
                 logger.debug(f"Could not extract {m}, defaulting to 0.0")

        # Check if we extracted ANYTHING useful. If all are 0, the report might be unreadable or wrong format.
        if all(v == 0.0 for v in extracted_data.values()):
             msg = "Unable to determine - No readable data found matching expected metrics."
             logger.warning(msg)
             return {"error": msg}

        # --- INSTANT PREDICTION ---
        input_df = pd.DataFrame([extracted_data])[MODEL_COLUMNS]
        
        pred_idx = MODEL.predict(input_df)[0]
        disease = LE.inverse_transform([pred_idx])[0]
        confidence = np.max(MODEL.predict_proba(input_df)) * 100
        
        logger.info(f"Prediction: {disease} ({confidence:.2f}%)")

        advice = RECS_DF[RECS_DF['Disease'] == disease].iloc[0]
        
        return {
            "condition": disease,
            "confidence": f"{confidence:.2f}",
            "diet": advice['Diet_Recommendation'],
            "workout": advice['Workout_Recommendation'],
            "precautions": advice['Precautions']
        }
    except Exception as e:
        logger.exception("Error during prediction process")
        return {"error": str(e)}
