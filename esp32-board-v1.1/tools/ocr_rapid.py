from rapidocr_onnxruntime import RapidOCR

img = "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/ssd1677_fig13_0.png"
engine = RapidOCR()
result, _ = engine(img)
if result:
    for box, text, score in result:
        print(f"{score:.2f}\t{text}\t{box}")
else:
    print("no result")
