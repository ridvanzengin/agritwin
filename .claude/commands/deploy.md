Deploy the latest main-branch code to the production server.

## Before starting

Read `.claude/deploy.config` for server connection details (SERVER_USER, SERVER_IP, SSH_KEY, DEPLOY_SCRIPT).
If the file does not exist, stop and tell the user to create it — see the template at the bottom of this skill.

## Step 1 — Pre-flight checks (run silently, show a summary)

Run these in parallel:

- `git status` in the monorepo root — working tree must be clean
- `git -C agriTwin-app log --oneline origin/main -5` — show what is on main
- `git -C agriTwin-app status` — confirm the app repo is on main and clean

If anything is uncommitted or unpushed, stop and tell the user what needs to be resolved first.

## Step 2 — Show deployment summary and ask for approval

Print a short summary:
- Repo: agriTwin-app
- Branch: main
- Last 3 commits (hash + message)
- Server: $SERVER_IP

Then ask: **"Deploy these commits to production? (yes / no)"**

Do NOT proceed until the user explicitly confirms.

## Step 3 — Run the deploy

SSH to the server and run the deploy script:

```
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP "bash $DEPLOY_SCRIPT 2>&1"
```

Stream all output to the user as it arrives. Do not suppress any lines.

## Step 4 — Report result

- **Success**: confirm which containers are now running (the final `ps` output from deploy.sh shows this).
- **Failure**: show the error, identify the failing step (pull / build / migrate / restart), and suggest the fix.

---

## Config file template

If `.claude/deploy.config` is missing, tell the user to create it at the monorepo root with these keys (fill in real values — this file is gitignored):

```
SERVER_USER=root
SERVER_IP=<your-server-ip>
SSH_KEY=~/.ssh/<your-key>
DEPLOY_SCRIPT=/opt/agritwin/deploy/scripts/deploy.sh
```
