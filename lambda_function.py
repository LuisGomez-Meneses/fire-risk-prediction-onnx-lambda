import json
import os
import io
import boto3
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.warp import reproject, Resampling
import onnxruntime as ort

s3 = boto3.client("s3")

def read_tif_from_s3(bucket, key):
    """Download GeoTIFF from S3 and return array + profile."""
    obj = s3.get_object(Bucket=bucket, Key=key)
    data_bytes = obj["Body"].read()
    with MemoryFile(data_bytes) as mem:
        with mem.open() as src:
            arr = src.read(1).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                arr = np.where(arr == nodata, np.nan, arr)
            profile = src.profile
    return arr, profile


def reproject_to_match(src_arr, src_prof, dst_prof):
    """Reproject src_arr so it matches dst_prof grid and transform."""
    dst_arr = np.empty((dst_prof["height"], dst_prof["width"]), dtype=np.float32)

    reproject(
        source=src_arr,
        destination=dst_arr,
        src_transform=src_prof["transform"],
        src_crs=src_prof["crs"],
        dst_transform=dst_prof["transform"],
        dst_crs=dst_prof["crs"],
        resampling=Resampling.bilinear
    )

    dst_arr[~np.isfinite(dst_arr)] = np.nan
    return dst_arr


def lambda_handler(event, context):

    # ======================================================
    # 1. SI LA LLAMADA VIENE DESDE API GATEWAY → LEER BODY
    # ======================================================
    if "body" in event:
        try:
            event = json.loads(event["body"])
        except Exception as e:
            raise ValueError(f"Invalid JSON from API Gateway: {e}")

    # ======================================================
    # 2. Leer parámetros del event (API o CLI)
    # ======================================================
    bucket    = event["bucket"]
    ndvi_key  = event["ndvi_key"]
    lst_key   = event["lst_key"]
    model_key = "model/xgb_fire_model.onnx"

    print(f"Loading NDVI: s3://{bucket}/{ndvi_key}")
    print(f"Loading LST:  s3://{bucket}/{lst_key}")
    print(f"Loading model: s3://{bucket}/{model_key}")

    # ======================================================
    # 3. Leer NDVI y LST desde S3
    # ======================================================
    NDVI, ndvi_prof = read_tif_from_s3(bucket, ndvi_key)
    LST, lst_prof  = read_tif_from_s3(bucket, lst_key)

    # ======================================================
    # 4. Convert LST to Celsius (MODIS scaling)
    # ======================================================
    LST_C = (LST * 0.02) - 273.15

    # ======================================================
    # 5. Reproyectar NDVI → LST
    # ======================================================
    print("Reprojecting NDVI to match LST grid...")
    NDVI_aligned = reproject_to_match(NDVI, ndvi_prof, lst_prof)

    # ======================================================
    # 6. Crear stack de features
    # ======================================================
    full_stack = np.stack([LST_C, NDVI_aligned], axis=-1)
    print("Stack shape:", full_stack.shape)

    # ======================================================
    # 7. Máscara de píxeles válidos
    # ======================================================
    mask = np.isfinite(full_stack).all(axis=-1)
    X = full_stack[mask].astype(np.float32)
    print("Valid pixels:", len(X))

    if len(X) == 0:
        raise ValueError("No valid pixels available for inference.")

    # ======================================================
    # 8. Cargar modelo ONNX desde S3
    # ======================================================
    model_obj = s3.get_object(Bucket=bucket, Key=model_key)
    model_bytes = model_obj["Body"].read()
    session = ort.InferenceSession(model_bytes)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[1].name

    # ======================================================
    # 9. Inferencia ONNX
    # ======================================================
    print("Running ONNX inference...")
    prob = session.run([output_name], {input_name: X})[0][:, 1]

    # ======================================================
    # 10. Reconstruir prob_map completo
    # ======================================================
    prob_map = np.full(mask.shape, np.nan, dtype=np.float32)
    prob_map[mask] = prob

    # ======================================================
    # 11. Guardar resultado en S3
    # ======================================================
    output_key = f"results/fire_prob_{os.path.basename(lst_key)}"

    out_prof = lst_prof.copy()
    out_prof.update({
        "dtype": "float32",
        "count": 1,
        "compress": "lzw"
    })

    memfile = MemoryFile()
    with memfile.open(**out_prof) as dst:
        dst.write(prob_map.astype(np.float32), 1)

    s3.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=memfile.read()
    )

    print(f"Generated output: s3://{bucket}/{output_key}")

    # ======================================================
    # 12. RESPUESTA (API + CLI)
    # ======================================================
    response = {
        "message": "Fire probability map generated",
        "input_NDVI": f"s3://{bucket}/{ndvi_key}",
        "input_LST": f"s3://{bucket}/{lst_key}",
        "output": f"s3://{bucket}/{output_key}"
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response)
    }


