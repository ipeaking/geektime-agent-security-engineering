"""Context Lab 使用的明确错误类型。"""


class ContextLabError(Exception):
    """Context Lab 可预期错误的基类。"""


class CaseLoadError(ContextLabError, ValueError):
    """Case 文件缺失、格式错误或字段非法。"""


class UnsupportedWrapperError(ContextLabError, ValueError):
    """请求了 Context Lab 不支持的包装方式。"""


class LocalOriginViolation(ContextLabError, ValueError):
    """网页请求试图离开本次实验的本地 Origin。"""
