from typing import Any


def success_response(data: Any, message: str = "成功", code: int = 0) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }
