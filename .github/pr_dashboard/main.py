import argparse
import dataclasses
import datetime
import json
import os
import pathlib

import commands
import github_api
import labels

LABEL_CONFIG_PATH = pathlib.Path(__file__).parent / "labels.toml"


def _print_outcome(outcome: commands.Outcome) -> None:
    print(json.dumps(dataclasses.asdict(outcome), indent=2))


def label_pr(repo: str, pr_number: int, dry_run: bool) -> None:
    label_config = labels.load_label_config(LABEL_CONFIG_PATH)
    pull_request = github_api.get_pull_request(repo, pr_number)
    outcome = commands.recompute_labels(label_config, pull_request, argument="")
    unreacted_outcome = dataclasses.replace(outcome, react=False)
    _print_outcome(unreacted_outcome)
    if not dry_run:
        github_api.apply_outcome(repo, pr_number, comment_id=None, outcome=unreacted_outcome)


def handle_comment(repo: str, event_path: str) -> None:
    with open(event_path) as event_file:
        event_data = json.load(event_file)
    if "pull_request" not in event_data["issue"]:
        return
    comment_body = event_data["comment"]["body"]
    if commands.parse_command(comment_body) is None:
        return
    pr_number = event_data["issue"]["number"]
    comment_author = event_data["comment"]["user"]["login"]
    comment = commands.Comment(
        comment_id=event_data["comment"]["id"],
        author=comment_author,
        author_has_write_access=github_api.user_has_write_access(repo, comment_author),
        body=comment_body,
    )
    label_config = labels.load_label_config(LABEL_CONFIG_PATH)
    pull_request = github_api.get_pull_request(repo, pr_number)
    open_milestones = github_api.list_open_milestones(repo)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    outcome = commands.handle_comment(label_config, pull_request, comment, open_milestones, today)
    _print_outcome(outcome)
    github_api.apply_outcome(repo, pr_number, comment_id=comment.comment_id, outcome=outcome)


def _label_sync_step(label_definition: labels.LabelDefinition, repo_labels: dict[str, dict]) -> tuple[str, str] | None:
    existing_label = repo_labels.get(label_definition.name)
    renamable_label = repo_labels.get(label_definition.renamed_from)
    if (existing_label is None) and (renamable_label is None):
        return "create", label_definition.name
    elif existing_label is None:
        return "rename", label_definition.renamed_from
    elif (
        (existing_label["color"].lower() == label_definition.color.lower())
        and (existing_label["description"] == label_definition.description)
    ):
        return None
    else:
        return "update", label_definition.name


def sync_label_set(repo: str, dry_run: bool) -> None:
    label_config = labels.load_label_config(LABEL_CONFIG_PATH)
    repo_labels = github_api.list_repo_labels(repo)
    for label_definition in label_config.label_definitions:
        sync_step = _label_sync_step(label_definition, repo_labels)
        if sync_step is None:
            continue
        sync_action, current_name = sync_step
        print(f"{sync_action} {current_name} -> {label_definition.name}")
        if dry_run:
            continue
        elif sync_action == "create":
            github_api.create_label(repo, label_definition.name, label_definition.color, label_definition.description)
        else:
            github_api.update_label(
                repo, current_name, label_definition.name, label_definition.color, label_definition.description
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
