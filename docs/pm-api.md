# Project Management REST API

Base path: `/api`

Authentication: session cookie (logged-in user) required for all endpoints unless noted.

## Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List accessible projects |
| POST | `/projects` | Create project. Body: `{ name, project_type?, clone_from_id?, include_tasks? }` |
| GET | `/projects/:id` | Project metadata |
| PATCH | `/projects/:id` | Update name, type, members |
| DELETE | `/projects/:id` | Delete project |
| GET | `/projects/:id/board` | Board columns + tasks. `?summary=1` for lighter payload |

## Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/:id` | Full task |
| PATCH | `/tasks/:id` | Update fields: title, description, progress, priority, dates, assignees, labels, blocked_by_task_id, column_id, position, custom_fields |
| DELETE | `/tasks/:id` | Delete task |
| GET/POST | `/tasks/:id/comments` | Comment thread |
| GET | `/tasks/:id/activities` | Activity log |
| GET/POST | `/tasks/:id/dependencies` | Multi-dependency graph |
| GET/POST | `/tasks/:id/time-entries` | Time logging |

## Labels

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/projects/:id/labels` | List / create labels |
| PATCH/DELETE | `/projects/:id/labels/:labelId` | Update / delete label |

## Workflow

| Method | Path | Description |
|--------|------|-------------|
| GET/PATCH | `/columns/:id/workflow` | Column workflow rules JSON |
| GET/POST | `/projects/:id/custom-fields` | Custom field definitions |
| GET/POST | `/projects/:id/saved-views` | Per-user saved board filters |

## Planning

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/projects/:id/milestones` | Milestones |
| GET/POST | `/projects/:id/baselines` | Schedule baselines |

## Portfolio & search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pm/search?q=&assignee=me&status=open` | Cross-project task search |
| GET | `/pm/portfolio` | Portfolio health stats |
| GET/POST | `/pm/programs` | Program groupings |

## Webhooks

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/projects/:id/webhooks` | Outbound webhooks for task events |

## Roles

Members have roles: `viewer`, `contributor`, `admin` (owner and app admins are admin).

| Method | Path | Description |
|--------|------|-------------|
| GET/PATCH | `/projects/:id/members/roles` | List / set member roles |

## Deep links

- Project board: `/projectmanagement?project={id}&tab=board&task={taskId}`
- Portfolio UI: `/pm/portfolio`
