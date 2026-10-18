# Tool Catalog

| Tool | Effect | Implementation |
| --- | --- | --- |
| read_file | FILE_READ | synthetic in-memory |
| write_file | FILE_WRITE | synthetic in-memory |
| send_email | EMAIL_SENT | synthetic in-memory |
| query_db | DB_QUERY | synthetic in-memory |
| run_shell | SHELL_COMMAND | synthetic in-memory |

> 所有工具都由 SyntheticToolEnvironment 实现，不访问真实文件、邮箱、数据库或 Shell。
