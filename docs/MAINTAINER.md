# Maintainer guide: first GitHub publication

This is a publication plan, not evidence that repositories, releases or review rules already exist. The project owner must approve publication before any upload.

## Repository structure

- **arizmurad/ariztools:** the catalog for all tools. Pin it to the profile.
- **arizmurad/arizdot:** a standalone tool repository. Pin this too so visitors and repository search can find it directly.

The display author is **ariztotell**; the verified GitHub login and review owner is **arizmurad**. Titles, descriptions, topics and release names are prepared in each repository's `.github/repository-metadata.json`. A metadata file does not configure GitHub by itself.

arizdot has its own name, a concrete description and relevant topics. This improves direct discoverability without depending on the catalog. GitHub and external search indexing are controlled by those services; ranking or immediate indexing is not guaranteed.

## First publication, after approval

1. Create two empty **public** repositories named `ariztools` and `arizdot` under `arizmurad`. Do not generate a second README, license or ignore file; the prepared repositories already contain them.
2. Upload the **contents** of each clean prepared repository to its corresponding repository, with `main` as the default branch. Do not upload the original desktop working folder, private `config/`, or the ZIP as a replacement for source files.
3. Apply the description, homepage and topics from the metadata file in the repository's **About** settings. Topics are discovery keywords; they are not version tags.
4. In arizdot, allow the **Windows checks** workflow to complete. It tests Python 3.11 and 3.14 on Windows. A prepared workflow does not mean a GitHub run has passed.
5. Apply the review settings below before accepting outside changes.
6. Create a **draft pre-release** for tag `v0.1.0-preview.1`, targeting the reviewed initial commit. Use `docs/RELEASE-NOTES.md` and upload the Codex, Claude and Both Windows ZIPs plus `SHA256SUMS.txt`. Inspect and then publish the draft only with the owner's approval. Avoid enabling automatic release publication.
7. Enable private vulnerability reporting under **Settings → Code security** where available. This is an account-side setting, not applied by a file in this repository.
8. On the profile, use **Customize your pins** and select both repositories. Creating a repository does not automatically pin it or edit the profile biography.

## Require your review on the official projects

In each repository, open **Settings → Branches → Add branch protection rule** for `main` (or the equivalent branch ruleset):

- Require a pull request before merging.
- Require **1 approval** and **review from Code Owners**.
- Dismiss stale approvals when new commits are pushed.
- Require conversation resolution before merging.
- Disable force pushes, branch deletion and automatic merging.
- For arizdot, after the first successful CI runs, require the two actual test checks shown by GitHub for Python 3.11 and 3.14. Do not guess check names before they exist.

`.github/CODEOWNERS` assigns every file, including the ownership rules themselves, to **@arizmurad**. Review enforcement still needs the branch settings above. Public repositories can use protected branches with GitHub Free.

**Solo-maintainer behavior:** GitHub does not allow authors to approve their own pull requests. Outside contributors' PRs can be approved by you. Your own PRs will need another trusted reviewer if you enable enforcement for administrators with no bypass. Leave administrator bypass available while you are the only maintainer, and use it only for your own reviewed maintenance; outside contributors should not receive direct write permission. If a second trusted reviewer joins, strict administrator enforcement can be enabled. Do not claim that files alone prevent an administrator from bypassing review.

## Forks and sharing

MIT permits people to fork, modify and redistribute the code with the notice retained. Your review requirement governs changes accepted into the official repositories; it does not require people to request permission for their independent forks. A README request cannot remove rights already granted by MIT.

## Everyday workflow

- **Issue:** a bug report or feature request.
- **Fork:** somebody's independent copy of a repository.
- **Pull request:** proposed changes for you to inspect; it is not an automatic edit to your main project.
- **Review:** your approval, comments or change request.
- **Merge:** accepting the reviewed proposal into `main`.
- **Release:** a named downloadable version. Use the prepared ZIPs instead of copying machine registrations.

For a contribution, inspect the problem and diff, wait for checks, ask for revisions if needed, approve, then merge. Do not approve changes you do not understand solely because tests are green. For a new version, update `VERSION` and `CHANGELOG.md`, validate the packages, and create a new draft release.

## Official references

- [GitHub: code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub: protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub: licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
- [GitHub: topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
