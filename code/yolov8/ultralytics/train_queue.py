import argparse
import json
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_QUEUE_FILE = BASE_DIR / "train_tasks.json"
DEFAULT_LOG_DIR = BASE_DIR / "train_queue_logs"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_conda_bat() -> str | None:
    candidates = [
        os.environ.get("CONDA_EXE"),
        r"C:\ProgramData\miniconda3\condabin\conda.bat",
        r"C:\Users\Admin\miniconda3\condabin\conda.bat",
        r"C:\ProgramData\anaconda3\condabin\conda.bat",
        r"C:\Users\Admin\anaconda3\condabin\conda.bat",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def load_tasks(queue_file: Path) -> list[dict]:
    if not queue_file.exists():
        return []
    return json.loads(queue_file.read_text(encoding="utf-8"))


def save_tasks(queue_file: Path, tasks: list[dict]) -> None:
    queue_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def make_task(command: str, cwd: str | None, name: str | None, conda_env: str | None) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "id": f"task_{timestamp}",
        "name": name or f"train_{timestamp}",
        "command": command,
        "cwd": cwd or str(BASE_DIR),
        "conda_env": conda_env,
        "status": "pending",
        "created_at": now_text(),
        "last_started_at": None,
        "last_finished_at": None,
        "return_code": None,
        "log_file": None,
        "error": None,
    }


def cmd_add(args: argparse.Namespace) -> None:
    queue_file = Path(args.queue_file)
    tasks = load_tasks(queue_file)
    task = make_task(args.command, args.cwd, args.name, args.conda_env)
    tasks.append(task)
    save_tasks(queue_file, tasks)
    print(f"已添加任务: {task['id']}  {task['name']}")


def cmd_list(args: argparse.Namespace) -> None:
    queue_file = Path(args.queue_file)
    tasks = load_tasks(queue_file)
    if not tasks:
        print("当前没有任务。")
        return
    for index, task in enumerate(tasks, start=1):
        print(
            f"[{index}] id={task['id']} | name={task['name']} | status={task['status']} | "
            f"env={task.get('conda_env') or '-'} | cwd={task['cwd']} | command={task['command']}"
        )


def cmd_remove(args: argparse.Namespace) -> None:
    queue_file = Path(args.queue_file)
    tasks = load_tasks(queue_file)
    remained = [task for task in tasks if task["id"] != args.task_id]
    if len(remained) == len(tasks):
        print(f"未找到任务: {args.task_id}")
        return
    save_tasks(queue_file, remained)
    print(f"已删除任务: {args.task_id}")


def cmd_clear(args: argparse.Namespace) -> None:
    queue_file = Path(args.queue_file)
    save_tasks(queue_file, [])
    print("任务队列已清空。")


def build_shell_command(task: dict) -> str:
    conda_env = task.get("conda_env")
    if conda_env:
        conda_bat = find_conda_bat()
        if not conda_bat:
            raise FileNotFoundError("未找到 conda.bat，请检查 Miniconda/Anaconda 安装路径。")
        return f'cmd /d /c ""{conda_bat}" run -n {conda_env} {task["command"]}"'
    return task["command"]


def run_one_task(task: dict, log_dir: Path) -> tuple[int, str]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{task['id']}.log"
    shell_command = build_shell_command(task)
    task["last_started_at"] = now_text()
    task["status"] = "running"
    task["log_file"] = str(log_path)
    task["error"] = None

    start = time.time()
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_text()}] START {task['name']}\n")
        f.write(f"COMMAND: {shell_command}\n")
        f.write(f"CWD: {task['cwd']}\n\n")
        process = subprocess.Popen(
            shell_command,
            cwd=task["cwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            f.write(line)
        return_code = process.wait()
        duration = time.time() - start
        f.write(f"\n[{now_text()}] END return_code={return_code} duration={duration:.1f}s\n")
    return return_code, str(log_path)


def cmd_run(args: argparse.Namespace) -> None:
    queue_file = Path(args.queue_file)
    log_dir = Path(args.log_dir)
    tasks = load_tasks(queue_file)
    if not tasks:
        print("当前没有任务可执行。")
        return

    pending_only = not args.run_all
    ran_any = False
    for task in tasks:
        if pending_only and task["status"] not in {"pending", "failed"}:
            continue

        ran_any = True
        print(f"\n开始执行: {task['id']} | {task['name']}")
        try:
            return_code, log_path = run_one_task(task, log_dir)
            task["return_code"] = return_code
            task["last_finished_at"] = now_text()
            task["log_file"] = log_path
            task["status"] = "done" if return_code == 0 else "failed"
            if return_code != 0:
                task["error"] = f"任务退出码为 {return_code}"
                print(f"任务失败，继续下一个: {task['id']}")
            else:
                print(f"任务完成: {task['id']}")
        except Exception as exc:
            task["status"] = "failed"
            task["return_code"] = -1
            task["last_finished_at"] = now_text()
            task["error"] = str(exc)
            print(f"任务异常，继续下一个: {task['id']} | {exc}")
        finally:
            save_tasks(queue_file, tasks)

    if not ran_any:
        print("没有符合条件的任务可执行。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="训练任务队列管理器")
    parser.add_argument(
        "--queue-file",
        default=str(DEFAULT_QUEUE_FILE),
        help="任务队列文件路径，默认是当前脚本目录下的 train_tasks.json",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    add_parser = subparsers.add_parser("add", help="添加一个训练任务")
    add_parser.add_argument("--name", help="任务名称")
    add_parser.add_argument("--cwd", help="命令执行目录")
    add_parser.add_argument("--conda-env", help="指定 conda 环境名，例如 yolov8")
    add_parser.add_argument("command", help='要执行的命令，例如: python tran.py')
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list", help="查看任务列表")
    list_parser.set_defaults(func=cmd_list)

    remove_parser = subparsers.add_parser("remove", help="删除指定任务")
    remove_parser.add_argument("task_id", help="任务 id")
    remove_parser.set_defaults(func=cmd_remove)

    clear_parser = subparsers.add_parser("clear", help="清空任务队列")
    clear_parser.set_defaults(func=cmd_clear)

    run_parser = subparsers.add_parser("run", help="顺序执行任务")
    run_parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="日志目录，默认是当前脚本目录下的 train_queue_logs",
    )
    run_parser.add_argument(
        "--run-all",
        action="store_true",
        help="默认只跑 pending 和 failed 任务；加上这个参数会把 done 任务也再执行一遍",
    )
    run_parser.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
