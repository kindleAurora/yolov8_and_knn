from ultralytics import YOLO
def main():
    model = YOLO(r"C:\Users\Admin\Desktop\毕设\runs\detect\cow_120_on_basecommon\weights\best.pt")
    results = model.track(source=r"C:\Users\Admin\Desktop\毕设\all_datasets\cow_video\一群奶牛在草地上吃草.mp4", show=True)

if __name__ == "__main__":
    main()