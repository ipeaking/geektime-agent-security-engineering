"""把不同外部载体转换成可追踪的统一内容封装。"""

from .adapters import AdapterRegistry
from .models import ContentEnvelope, ContentSource

__all__ = ["AdapterRegistry", "ContentEnvelope", "ContentSource"]
