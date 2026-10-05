# Security policy

Version 1.0.x is supported. Report vulnerabilities privately using GitHub's
**Report a vulnerability** action on this repository when private reporting is
enabled. Before publishing, enable private vulnerability reporting under the
repository security settings. If it is unavailable, contact the repository owner
privately through their profile rather than posting exploitable details publicly.

Include affected versions, steps using isolated dummy files, expected behavior,
and impact. Never include personal files, passwords, `.env` values, or tokens.

This project is a trusted local filesystem tool, not a public file hosting service.
All approved roots are shared by accounts. Run on loopback, use a dedicated OS user
with limited permissions, keep dependencies updated, and review scheduled access.
Demo users and passwords are development only. Password hashes, CSRF, role checks,
path approval, file verification, and no-overwrite moves are implemented, but hostile
concurrent filesystem changes are outside its isolation model. See README safety
and limitations for interrupted-copy recovery and deployment requirements.
