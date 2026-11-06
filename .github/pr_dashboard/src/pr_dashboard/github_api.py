import json
import subprocess
import urllib.parse

from pr_dashboard import pr_types


def _gh_api(
    *,
    endpoint: str,
    method: str = "GET",
    fields: dict | None = None,
    paginate: bool = False,
):
    cmd_parts = ["gh", "api", "--method", method, endpoint]
    if paginate:
        cmd_parts.append("--paginate")
        cmd_parts.append("--slurp")
    if fields is None:
        input_text = None
    else:
        cmd_parts.extend(["--input", "-"])
        input_text = json.dumps(fields)
    completed_process = subprocess.run(
        cmd_parts,
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )
    if completed_process.stdout.strip() == "":
        return None
    else:
        return json.loads(completed_process.stdout)


def _quote(
    path_part: str,
) -> str:
    return urllib.parse.quote(path_part, safe="")


def get_pull_request(
    *,
    repo: str,
    pr_number: int,
) -> pr_types.PullRequest:
    pr_data = _gh_api(endpoint=f"repos/{repo}/pulls/{pr_number}")
    file_pages = _gh_api(
        endpoint=f"repos/{repo}/pulls/{pr_number}/files?per_page=100",
        paginate=True,
    )
    edited_file_paths = tuple(
        _file_data["filename"] for _file_page in file_pages for _file_data in _file_page
    )
    return pr_types.PullRequest(
        pr_number=pr_number,
        author=pr_data["user"]["login"],
        assignees=tuple(_assignee["login"] for _assignee in pr_data["assignees"]),
        label_names=tuple(_label_data["name"] for _label_data in pr_data["labels"]),
        num_lines_changed=pr_data["additions"] + pr_data["deletions"],
        edited_file_paths=edited_file_paths,
    )


def get_user(
    *,
    repo: str,
    user_name: str,
) -> pr_types.User:
    try:
        permission_data = _gh_api(endpoint=f"repos/{repo}/collaborators/{_quote(user_name)}/permission")
        role_in_repo = pr_types.RoleInRepo(permission_data["role_name"])
    except (subprocess.CalledProcessError, ValueError):
        role_in_repo = pr_types.RoleInRepo.READ
    return pr_types.User(
        user_name=user_name,
        role_in_repo=role_in_repo,
    )


def list_open_milestones(
    repo: str,
) -> tuple[pr_types.Milestone, ...]:
    milestone_pages = _gh_api(
        endpoint=f"repos/{repo}/milestones?state=open&per_page=100",
        paginate=True,
    )
    return tuple(
        pr_types.Milestone(
            milestone_number=_milestone_data["number"],
            title=_milestone_data["title"],
        ) for _milestone_page in milestone_pages for _milestone_data in _milestone_page
    )


def list_repo_labels(
    repo: str,
) -> dict[str, dict]:
    label_pages = _gh_api(
        endpoint=f"repos/{repo}/labels?per_page=100",
        paginate=True,
    )
    return {_label_data["name"]: _label_data for _label_page in label_pages for _label_data in _label_page}


def create_label(
    *,
    repo: str,
    name: str,
    color: str,
    description: str,
) -> None:
    label_fields = {"name": name, "color": color, "description": description}
    _gh_api(
        endpoint=f"repos/{repo}/labels",
        method="POST",
        fields=label_fields,
    )


def update_label(
    *,
    repo: str,
    name: str,
    color: str,
    description: str,
) -> None:
    label_fields = {"color": color, "description": description}
    _gh_api(
        endpoint=f"repos/{repo}/labels/{_quote(name)}",
        method="PATCH",
        fields=label_fields,
    )


def apply_update_plan(
    *,
    repo: str,
    pr_number: int,
    comment_id: int | None,
    update_plan: pr_types.UpdatePlan,
) -> None:
    issue_endpoint = f"repos/{repo}/issues/{pr_number}"
    for label_name in update_plan.label_names_to_remove:
        _gh_api(
            endpoint=f"{issue_endpoint}/labels/{_quote(label_name)}",
            method="DELETE",
        )
    if len(update_plan.label_names_to_add) > 0:
        _gh_api(
            endpoint=f"{issue_endpoint}/labels",
            method="POST",
            fields={"labels": list(update_plan.label_names_to_add)},
        )
    if len(update_plan.assignees_to_remove) > 0:
        assignee_fields = {"assignees": list(update_plan.assignees_to_remove)}
        _gh_api(
            endpoint=f"{issue_endpoint}/assignees",
            method="DELETE",
            fields=assignee_fields,
        )
    if len(update_plan.assignees_to_add) > 0:
        assignee_fields = {"assignees": list(update_plan.assignees_to_add)}
        _gh_api(
            endpoint=f"{issue_endpoint}/assignees",
            method="POST",
            fields=assignee_fields,
        )
    if update_plan.milestone_change is not None:
        milestone_fields = {"milestone": update_plan.milestone_change.milestone_number}
        _gh_api(
            endpoint=issue_endpoint,
            method="PATCH",
            fields=milestone_fields,
        )
    if update_plan.reply is not None:
        _gh_api(
            endpoint=f"{issue_endpoint}/comments",
            method="POST",
            fields={"body": update_plan.reply},
        )
    if update_plan.react and (comment_id is not None):
        _gh_api(
            endpoint=f"repos/{repo}/issues/comments/{comment_id}/reactions",
            method="POST",
            fields={"content": "+1"},
        )
