import time
from ultralytics import YOLO


def main():
    # wait_seconds = 200 * 60
    # print("程序已启动，1小时后开始训练...")
    # time.sleep(wait_seconds)

    print("开始训练...")
    model = YOLO(r"C:\Users\Admin\Desktop\毕设\code\yolov8\ultralytics\yolo26n.pt")

    model.train(
        data="cowdata.yaml",
        epochs=150,
        imgsz=640,
        batch=30,
        workers=8
    )


if __name__ == "__main__":
    main()
