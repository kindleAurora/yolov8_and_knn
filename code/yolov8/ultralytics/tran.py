# from ultralytics import YOLO

# def main():
#     # Load a model
#     model = YOLO("yolov8n.yaml")  # build a new model from YAML
#     # model = YOLO("yolo26n.pt")  # load a pretrained model (recommended for training)
#     # model = YOLO("yolo26n.yaml").load("yolo26n.pt")  # build from YAML and transfer weights

#     # Train the model
#     results = model.train(data="mydata.yaml", epochs=300, imgsz=640,batch = 50,workers=8)

# if __name__ == "__main__":
#     main()

# from ultralytics import YOLO
# from pathlib import Path


# def main():
#     project_root = Path(r"C:\Users\Admin\Desktop\毕设")
#     last_ckpt = project_root / r"runs\detect\train2\weights\last.pt"

#     if not last_ckpt.exists():
#         raise FileNotFoundError(f"没找到断点权重: {last_ckpt}")

#     model = YOLO(str(last_ckpt))
#     model.train(resume=True,
                
#                 )  # 从 epoch 90 继续到你上次设定的 epochs=100


# if __name__ == "__main__":
#     main()

# 迁移训练
from ultralytics import YOLO

def main():
    # Load a model

    model = YOLO(r"C:\Users\Admin\Desktop\毕设\runs\detect\train19\weights\best.pt")  # load a pretrained model (recommended for training)


    # Train the model
    results = model.train(data="cowdata.yaml", epochs=120, imgsz=832,batch = 20,workers=6)

if __name__ == "__main__":
    main()
