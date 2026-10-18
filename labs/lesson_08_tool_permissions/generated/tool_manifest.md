# Tool Permission Manifest

| Tool | Capabilities | Arguments |
| --- | --- | --- |
| read_file | READ | path |
| write_file | WRITE | path, content |
| send_email | WRITE, NETWORK | to, subject, body |
| query_db | READ | query_id |
| run_shell | EXECUTE | command |
| charge_payment | PAYMENT, NETWORK | amount, currency, memo |
| manage_users | ADMIN, WRITE | user_id, action |
