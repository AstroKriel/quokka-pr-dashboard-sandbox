import argparse
import dataclasses
import datetime
import json
import os
import pathlib

import commands
import github_api
import labels

LABELS_TOML_PATH = pathlib.Path(__file__).parents[1] / "labels.toml"


def _print_update_plan(
    update_plan: commands.UpdatePlan,
) -> None:
    print(
        json.dumps(
            dataclasses.asdict(update_plan),
            indent=2,
        ),
    )


def label_pr(
    repo: str,
    pr_number: int,
    dry_run: bool,
) -> None:
    configured_labels = labels.load_configured_labels(LABELS_TOML_PATH)
    pull_request = github_api.get_pull_request(repo, pr_number)
    update_plan = commands.recompute_labels(configured_labels, pull_request, argument="")
    unreacted_update_plan = dataclasses.replace(update_plan, react=False)
    _print_update_plan(unreacted_update_plan)
    if not dry_run:
        github_api.apply_update_plan(
            repo,
            pr_number,
            comment_id=None,
            update_plan=unreacted_update_plan,
        )


def handle_comment(
    repo: str,
    event_path: str,
) -> None:
    with open(event_path) as event_file:
        event_data = json.load(event_file)
    if "pull_request" not in event_data["issue"]:
        return
    comment_text = event_data["comment"]["body"]
    if commands.parse_command(comment_text) is None:
        return
    pr_number = event_data["issue"]["number"]
    user = github_api.get_user(repo, event_data["comment"]["user"]["login"])
    comment = commands.Comment(
        comment_id=event_data["comment"]["id"],
        user=user,
        text=comment_text,
    )
    configured_labels = labels.load_configured_labels(LABELS_TOML_PATH)
    pull_request = github_api.get_pull_request(repo, pr_number)
    open_milestones = github_api.list_open_milestones(repo)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    update_plan = commands.handle_comment(configured_labels, pull_request, comment, open_milestones, today)
    _print_update_plan(update_plan)
    github_api.apply_update_plan(
        repo,
        pr_number,
        comment_id=comment.comment_id,
        update_plan=update_plan,
    )


def _label_sync_step(
    label: labels.Label,
    repo_labels: dict[str, dict],
) -> str | None:
    existing_label_data = repo_labels.get(label.name)
    if existing_label_data is None:
        return "create"
    elif ((existing_label_data["color"].lower() == label.color.lower())
          and (existing_label_data["description"] == label.description)):
        return None
    else:
        return "update"


def sync_label_set(
    repo: str,
    dry_run: bool,
) -> None:
    configured_labels = labels.load_configured_labels(LABELS_TOML_PATH)
    repo_labels = github_api.list_repo_labels(repo)
    for label in configured_labels.all_labels():
        sync_action = _label_sync_step(label, repo_labels)
        if sync_action is None:
            continue
        print(f"{sync_action} {label.name}")
        if dry_run:
            continue
        elif sync_action == "create":
            github_api.create_label(
                repo,
                label.name,
                label.color,
                label.description,
            )
        else:
            github_api.update_label(
                repo,
                label.name,
                label.color,
                label.description,
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
        label_pr(parsed_args.repo, parsed_args.pr, parsed_args.dry_run)
    elif parsed_args.action == "handle-comment":
        handle_comment(parsed_args.repo, parsed_args.event_path)
    else:
        sync_label_set(parsed_args.repo, parsed_args.dry_run)


if __name__ == "__main__":
    main()
