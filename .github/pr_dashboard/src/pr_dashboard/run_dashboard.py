import argparse
import dataclasses
import datetime
import json
import os
import pathlib

from pr_dashboard import github_api
from pr_dashboard import handle_commands
from pr_dashboard import label_types
from pr_dashboard import load_labels
from pr_dashboard import pr_types

LABELS_TOML_PATH = pathlib.Path(__file__).parents[2] / "labels.toml"


def print_update_plan(
    update_plan: pr_types.UpdatePlan,
) -> None:
    print(
        json.dumps(
            dataclasses.asdict(update_plan),
            indent=2,
        ),
    )


def label_pr(
    *,
    repo: str,
    pr_number: int,
    dry_run: bool,
) -> None:
    configured_labels = load_labels.load_configured_labels(LABELS_TOML_PATH)
    pull_request = github_api.get_pull_request(
        repo=repo,
        pr_number=pr_number,
    )
    update_plan = handle_commands.recompute_labels(
        configured_labels=configured_labels,
        pull_request=pull_request,
        argument="",
    )
    unreacted_update_plan = dataclasses.replace(update_plan, react=False)
    print_update_plan(unreacted_update_plan)
    if not dry_run:
        github_api.apply_update_plan(
            repo=repo,
            pr_number=pr_number,
            comment_id=None,
            update_plan=unreacted_update_plan,
        )


def run_comment_command(
    *,
    repo: str,
    event_path: str,
) -> None:
    with open(event_path) as event_file:
        event_data = json.load(event_file)
    if "pull_request" not in event_data["issue"]:
        return
    comment_text = event_data["comment"]["body"]
    if handle_commands.parse_command(comment_text) is None:
        return
    pr_number = event_data["issue"]["number"]
    commenter_user_name = event_data["comment"]["user"]["login"]
    user = github_api.get_user(
        repo=repo,
        user_name=commenter_user_name,
    )
    comment = pr_types.Comment(
        comment_id=event_data["comment"]["id"],
        user=user,
        text=comment_text,
    )
    configured_labels = load_labels.load_configured_labels(LABELS_TOML_PATH)
    pull_request = github_api.get_pull_request(
        repo=repo,
        pr_number=pr_number,
    )
    open_milestones = github_api.list_open_milestones(repo)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    update_plan = handle_commands.handle_comment(
        configured_labels=configured_labels,
        pull_request=pull_request,
        comment=comment,
        open_milestones=open_milestones,
        today=today,
    )
    print_update_plan(update_plan)
    github_api.apply_update_plan(
        repo=repo,
        pr_number=pr_number,
        comment_id=comment.comment_id,
        update_plan=update_plan,
    )


def get_label_sync_action(
    *,
    label: label_types.Label,
    repo_labels: dict[str, dict],
) -> str | None:
    existing_label_data = repo_labels.get(label.full_name)
    if existing_label_data is None:
        return "create"
    elif ((existing_label_data["color"].lower() == label.color.lower())
          and (existing_label_data["description"] == label.description)):
        return None
    else:
        return "update"


def sync_label_set(
    *,
    repo: str,
    dry_run: bool,
) -> None:
    configured_labels = load_labels.load_configured_labels(LABELS_TOML_PATH)
    repo_labels = github_api.list_repo_labels(repo)
    for label in configured_labels.all_labels():
        sync_action = get_label_sync_action(
            label=label,
            repo_labels=repo_labels,
        )
        if sync_action is None:
            continue
        print(f"{sync_action} {label.full_name}")
        if dry_run:
            continue
        elif sync_action == "create":
            github_api.create_label(
                repo=repo,
                name=label.full_name,
                color=label.color,
                description=label.description,
            )
        else:
            github_api.update_label(
                repo=repo,
                name=label.full_name,
                color=label.color,
                description=label.description,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["label-pr", "handle-comment", "sync-label-set"])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--dry-run", action="store_true")
    parsed_args = parser.parse_args()
    if parsed_args.action == "label-pr":
        label_pr(
            repo=parsed_args.repo,
            pr_number=parsed_args.pr,
            dry_run=parsed_args.dry_run,
        )
    elif parsed_args.action == "handle-comment":
        run_comment_command(
            repo=parsed_args.repo,
            event_path=parsed_args.event_path,
        )
    else:
        sync_label_set(
            repo=parsed_args.repo,
            dry_run=parsed_args.dry_run,
        )


if __name__ == "__main__":
    main()
