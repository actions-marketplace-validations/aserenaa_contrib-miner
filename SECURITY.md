# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub's private vulnerability reporting](https://github.com/aserenaa/contrib-miner/security/advisories/new)
(**Security → Report a vulnerability**). Do not open a public issue.

Include the contrib-miner version or commit, how you ran it (action or command line) and the
steps to reproduce. **Never include a token.** Fixes land on `main` and in the next `v1` release,
which is the only supported version.

## What contrib-miner touches

| What | How |
|---|---|
| GitHub token | Read from the `github_token` input, `--token`, `GITHUB_TOKEN` or `GH_TOKEN`. Sent only to `https://api.github.com/graphql`, never logged and never written to disk. |
| Contribution data | Fetched for one login, kept in memory, and only drawn into the GIF. |
| Output | A single GIF at the path you choose. |

## Threat model notes

- **Token scope.** The default `github.token` only reads public data, which is all most profiles
  need. A personal access token for private contributions needs only `read:user`. Store it as an
  Actions secret and never commit it.
- **Publishing.** The example workflow force-pushes the GIF to a dedicated `output` branch with the
  job's own token and `contents: write`. It never pushes to your default branch.
- **Pinned actions.** Workflows pin third-party actions to full commit SHAs, and Dependabot proposes
  updates. Pin `aserenaa/contrib-miner` to a SHA too if you want the same guarantee.
