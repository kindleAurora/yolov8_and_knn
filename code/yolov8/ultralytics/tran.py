# from ultralytics import YOLO

# def main():
#     # Load a model
#     model = YOLO("yolov8n.yaml")  # build a new model from YAML
#     # model = YOLO("yolo26n.pt")  # load a pretrained model (recommended for training)
#     # model = YOLO("yolo26n.yaml").load("yolo26n.pt")  # build from YAML and transfer weights

#     # Train the model
#     results = model.train(data="mydata.yaml", epochs=100, imgsz=640,batch = 20)

# if __name__ == "__main__":
#     main()
from ultralytics import YOLO
from pathlib import Path


def main():
    project_root = Path(r"C:\Users\17317\Desktop\project\薄老师深度学习\ultralytics")
    last_ckpt = project_root / r"runs\detect\train7\weights\last.pt"

    if not last_ckpt.exists():
        raise FileNotFoundError(f"没找到断点权重: {last_ckpt}")

    model = YOLO(str(last_ckpt))
    model.train(resume=True,
                workers=0,        # Windows 建议 0 或 2
                close_mosaic=0,   # 避免再次 reset dataloader
                batch=12,         # 20 太激进，先降
                )  # 从 epoch 90 继续到你上次设定的 epochs=100


if __name__ == "__main__":
    main()
