"""允许通过 ``python -m agent_security.context_lab`` 运行实验。"""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
