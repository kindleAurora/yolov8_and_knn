import time
from ultralytics import YOLO


def main():
    # wait_seconds = 60 * 60
    # print("程序已启动，1小时后开始训练...")
    # time.sleep(wait_seconds)

    print("开始训练...")
    model = YOLO("yolov8n.yaml")

    model.train(
        data="cowdata.yaml",
        epochs=200,
        imgsz=832,
        batch=20,
        workers=6
    )


if __name__ == "__main__":
    main()
