# Module 1: The Auditor — Detailed Specification

## Core Design Principle

**Assume nothing about the target environment.**

The Auditor must function correctly in ANY AWS environment, regardless of:

- No naming conventions (resources named `prod-db-1` or `asdf123` or unnamed)
- No Terraform / OpenTofu / CloudFormation — resources may be 100% ClickOps (console-created)
- No tags, no cost allocation tags, no organization structure
- Mixed architectures — some services IaC-managed, some manual, some abandoned
- Sprawling accounts with years of accumulated resources, orphaned infrastructure, and shadow IT
- Resources in unexpected regions, cross-account dependencies, or non-standard VPC layouts
- No documentation, no architecture diagrams, no CMDB

The Auditor must discover, classify, and analyze everything purely from the AWS APIs. It reads the infrastructure as-is — it doesn't need the customer to prepare, clean up, or explain anything.

---

## 1. Onboarding — Minimal Friction, Minimal Permissions

### 1.1 Onboarding Flow

The entire onboarding should take **under 5 minutes** and require no AWS expertise from the person doing it.

```
Step 1: Sign up on SafeScale web app
         ↓
Step 2: Click "Connect AWS Account"
         ↓
Step 3: SafeScale provides a CloudFormation one-click deploy link
        (or a Terraform module, or manual IAM instructions — customer's choice)
         ↓
Step 4: Customer deploys the stack → creates a cross-account IAM Role
        with a unique External ID
         ↓
Step 5: SafeScale assumes the role, runs a connectivity test,
        confirms access, and immediately starts the first audit scan
         ↓
Done.
```

### 1.2 Permission Tiers — Progressive Trust Model

Permissions expand only as the customer moves deeper into the product. The Auditor never needs more than Tier 1.

#### Tier 1: Discovery (Auditor Only) — Initial Onboarding

**Purpose:** Read-only discovery of infrastructure topology and cost data. This is all the Auditor needs.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SafeScaleDiscovery",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "rds:Describe*",
        "rds:ListTagsForResource",
        "elasticache:Describe*",
        "elasticache:ListTagsForResource",
        "eks:Describe*",
        "eks:List*",
        "ecs:Describe*",
        "ecs:List*",
        "elasticloadbalancing:Describe*",
        "opensearch:Describe*",
        "opensearch:List*",
        "kafka:Describe*",
        "kafka:List*",
        "efs:Describe*",
        "s3:GetBucketLocation",
        "s3:ListAllMyBuckets",
        "tag:GetResources",
        "tag:GetTagKeys",
        "tag:GetTagValues",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "cur:DescribeReportDefinitions",
        "organizations:DescribeOrganization",
        "organizations:ListAccounts",
        "iam:GetRole",
        "iam:ListRolePolicies",
        "sts:GetCallerIdentity",
        "route53:ListHostedZones",
        "route53:ListResourceRecordSets",
        "servicequotas:ListServiceQuotas"
      ],
      "Resource": "*"
    }
  ]
}
```

**What this allows:** Read everything, modify nothing. The customer can verify this — the policy contains zero write/create/delete/update actions.

**Trust signal for the customer:** "We can see your infrastructure but can't touch it. This is a read-only scan."

#### Tier 2: Protection Setup (Safety Net Module — Later)

Granted only when the customer approves a conversion plan. Adds:
- `rds:CreateDBSnapshot`, `rds:CopyDBSnapshot`
- `s3:PutObject`, `s3:CreateBucket` (for backup vaults)
- `elasticache:CreateSnapshot`
- `ec2:CreateSnapshot`

#### Tier 3: Conversion Execution (SafeScale Advisor — Later)

Granted only when the customer explicitly approves a specific conversion. Adds:
- `rds:ModifyDBInstance` (to disable Multi-AZ)
- `elasticache:ModifyReplicationGroup`
- `eks:UpdateNodegroupConfig`
- `ec2:ModifyInstanceAttribute`

#### Tier 4: Recovery Execution (Safety Net Failover — Later)

Granted only when recovery capability is being set up. Adds:
- `rds:RestoreDBInstanceToPointInTime`
- `ec2:RunInstances`, `ec2:CreateVolume`
- `eks:CreateNodegroup`
- `route53:ChangeResourceRecordSets`

**Key design principle:** Each tier is a separate CloudFormation stack / IAM policy that the customer deploys individually. They never grant more access than the current stage requires.

### 1.3 Multi-Account Support

Many mid-market companies have multiple AWS accounts (dev, staging, production, shared services). The onboarding should support:

- **Single account:** One IAM role, one scan
- **AWS Organizations:** Deploy a StackSet across all member accounts from the management account — one click to onboard the entire org
- **Manual multi-account:** Customer deploys the CloudFormation stack in each account individually

The Auditor treats each account as an independent scan target and aggregates results into a single dashboard view.

---

## 2. Discovery Engine — How the Auditor Works

### 2.1 Discovery Strategy: API-First, Assumption-Free

The Auditor does NOT rely on:
- Terraform state files (may not exist)
- CloudFormation stacks (resources may be manual)
- Tags (may be missing or inconsistent)
- Naming conventions (may be random)
- Documentation (may be outdated or nonexistent)

Instead, it queries **raw AWS APIs** and builds the topology graph from scratch:

```
┌─────────────────────────────────────────────────────────┐
│                   DISCOVERY PIPELINE                     │
│                                                         │
│  Phase 1: Resource Enumeration                          │
│  ├── Query each AWS service API (Describe*/List*)       │
│  ├── Enumerate across ALL active regions                │
│  ├── Collect resource metadata, configs, and tags       │
│  └── Build raw resource inventory                       │
│                                                         │
│  Phase 2: Topology Mapping                              │
│  ├── Resolve VPC/Subnet/AZ placement per resource       │
│  ├── Map security group connections                     │
│  ├── Trace IAM role assumptions and cross-service refs  │
│  ├── Identify load balancer → target group → instance   │
│  ├── Map EKS cluster → node group → pod dependencies    │
│  └── Build dependency graph                             │
│                                                         │
│  Phase 3: HA Classification                             │
│  ├── Detect Multi-AZ flags per resource                 │
│  │   (RDS MultiAZ, ElastiCache NumNodeGroups,           │
│  │    EKS subnets across AZs, etc.)                     │
│  ├── Classify: Built-In HA / Eligible / Ineligible      │
│  ├── Detect cross-AZ data paths (network flow logs)     │
│  └── Flag unknown/ambiguous configurations              │
│                                                         │
│  Phase 4: Cost Analysis                                 │
│  ├── Pull Cost Explorer data (last 30/60/90 days)       │
│  ├── Map costs to individual resources where possible   │
│  ├── Estimate per-resource HA surcharge                 │
│  ├── Calculate cross-AZ data transfer costs             │
│  └── Generate savings projections per resource          │
│                                                         │
│  Phase 5: Criticality Inference                         │
│  ├── Infer service tier from traffic patterns           │
│  │   (CloudWatch metrics: connections, requests,        │
│  │    CPU utilization, error rates)                     │
│  ├── Detect dependencies (if DB serves many services    │
│  │   → likely Tier-1)                                   │
│  ├── Flag resources with no recent activity (zombie)    │
│  └── Suggest criticality tier (customer confirms)       │
│                                                         │
│  Phase 6: Report Generation                             │
│  ├── Aggregate findings into structured report          │
│  ├── Calculate total eligible savings                   │
│  ├── Rank resources by savings potential                │
│  └── Generate the customer-facing Savings Report        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Region Scanning

The Auditor must scan ALL enabled AWS regions, not just the "expected" ones. Resources may exist in forgotten regions. The scan:

1. Calls `ec2:DescribeRegions` to get all enabled regions
2. Runs discovery in each region in parallel
3. Reports any resources found in unexpected regions as part of the audit

### 2.3 Handling Messy Environments

| Messy Scenario | How the Auditor Handles It |
|----------------|---------------------------|
| Resources with no tags | Classify by API metadata alone (instance type, config, metrics). Tags are bonus data, not required. |
| Resources with no names | Use resource ID (ARN) as the primary identifier. Show type + ID + region in all UIs. |
| Orphaned resources (running but unused) | Detect via CloudWatch metrics — zero connections, zero CPU, zero requests over 30 days. Flag as "zombie" in the report. |
| Cross-account dependencies | Detect via IAM role trust policies, VPC peering, PrivateLink endpoints. Note as "external dependency — manual review needed." |
| Resources created via CLI/Console (no IaC) | Treated identically to IaC-managed resources. The Auditor doesn't care how a resource was created. |
| Inconsistent Multi-AZ configs | Flag as "mixed configuration" — e.g., RDS is Multi-AZ but its EBS volumes are single-AZ. Surface contradictions explicitly. |
| Very large environments (1000+ resources) | Paginate all API calls. Use parallel region scanning. Implement backoff for API throttling. Show progress clearly. |
| Rate limiting / API throttling | Exponential backoff with jitter. Per-service rate tracking. Progress UI shows when throttling is occurring. |

### 2.4 Dependency Inference Without Tags or Documentation

Since we can't rely on tags or names, the Auditor infers dependencies from:

1. **Network topology:** Security group rules (which resources can talk to which), VPC/subnet placement, NACLs
2. **Load balancer targets:** ALB/NLB target groups point to specific instances/IPs/ECS services
3. **EKS/ECS service discovery:** Service definitions reference specific RDS endpoints, Redis endpoints, etc.
4. **IAM role chains:** If an EC2 instance's IAM role has `rds:*` permissions on a specific DB ARN, they're linked
5. **CloudWatch metrics correlation:** Resources with correlated traffic patterns (request spike on service A matches connection spike on DB B) are likely dependent
6. **DNS records:** Route53 records point to specific resources — maps the traffic path
7. **Environment variables and secrets:** (Tier 2+ permissions) SSM Parameter Store and Secrets Manager entries may contain connection strings linking services

The dependency graph is presented as a **suggestion** — the customer confirms or corrects it in the UI before any optimization proposals are generated.

---

## 3. Progress UI — Real-Time Audit Visibility

### 3.1 Design Principle

The customer should **never wonder what the Auditor is doing**. Every step is visible, timed, and logged.

### 3.2 Progress UI Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  SAFESCALE AUDITOR — Scanning: AWS Account 123456789012              │
│  Started: 2027-03-15 14:22:03 UTC    Elapsed: 4m 32s                │
│                                                                      │
│  Overall Progress  ████████████████░░░░░░░░░░░░░░  62%              │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  PHASE 1: Resource Enumeration               ✅ Complete 1m12s │  │
│  │  ├── us-east-1 ........... 247 resources     ✅ 0m38s          │  │
│  │  ├── us-west-2 ........... 84 resources      ✅ 0m22s          │  │
│  │  ├── eu-west-1 ........... 12 resources      ✅ 0m08s          │  │
│  │  ├── ap-southeast-1 ...... 0 resources       ✅ 0m04s          │  │
│  │  └── (13 other regions) .. 0 resources       ✅ 0m00s          │  │
│  │                                                                │  │
│  │  PHASE 2: Topology Mapping                   ✅ Complete 1m44s │  │
│  │  ├── VPC/Subnet mapping .................... ✅                │  │
│  │  ├── Security group analysis ............... ✅                │  │
│  │  ├── Load balancer → target resolution ..... ✅                │  │
│  │  ├── EKS cluster → node group mapping ...... ✅                │  │
│  │  └── Dependency graph: 343 resources, 891 edges                │  │
│  │                                                                │  │
│  │  PHASE 3: HA Classification                  🔄 In Progress    │  │
│  │  ├── RDS instances (8/8) ................... ✅                │  │
│  │  ├── ElastiCache clusters (3/3) ............ ✅                │  │
│  │  ├── EKS node groups (4/6) ................ 🔄 Scanning...    │  │
│  │  ├── EC2 Auto Scaling Groups (0/12) ........ ⏳ Pending        │  │
│  │  └── EBS Volumes (0/47) .................... ⏳ Pending        │  │
│  │                                                                │  │
│  │  PHASE 4: Cost Analysis                      ⏳ Pending        │  │
│  │  PHASE 5: Criticality Inference              ⏳ Pending        │  │
│  │  PHASE 6: Report Generation                  ⏳ Pending        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ LIVE LOG ───────────────────────────────────────────────────┐    │
│  │ 14:26:35  [HA-CLASSIFY] RDS: db-prod-main is Multi-AZ ✅     │    │
│  │ 14:26:35  [HA-CLASSIFY] RDS: db-analytics is Single-AZ       │    │
│  │ 14:26:36  [HA-CLASSIFY] ElastiCache: redis-session — 2 nodes │    │
│  │           across 2 AZs (us-east-1a, us-east-1b) → Multi-AZ   │    │
│  │ 14:26:37  [HA-CLASSIFY] EKS: cluster-prod — node group       │    │
│  │           "workers" spans 3 AZs → Multi-AZ eligible           │    │
│  │ 14:26:38  [THROTTLE] ec2:DescribeInstances — rate limited,    │    │
│  │           backing off 2.4s                                    │    │
│  │ 14:26:40  [HA-CLASSIFY] EKS: cluster-prod — node group       │    │
│  │           "monitoring" spans 1 AZ → already Single-AZ         │    │
│  │                                                               │    │
│  │  ▼ Auto-scrolling (click to pause)                            │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ RUNNING TOTALS ─────────────────────────────────────────────┐    │
│  │  Resources Discovered: 343  │  Multi-AZ Eligible: 47         │    │
│  │  Regions with Resources: 3  │  Estimated Savings: calculating │    │
│  │  Dependencies Mapped: 891   │  Zombies Found: 12             │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  [ Pause Scan ]  [ Export Log ]  [ Cancel ]                          │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Progress UI Behaviors

| Feature | Description |
|---------|-------------|
| **Phase-level progress bars** | Each phase shows progress as a percentage with sub-task breakdown |
| **Per-resource status icons** | ✅ Complete, 🔄 In Progress, ⏳ Pending, ⚠️ Warning (throttled/partial), ❌ Error |
| **Live log stream** | Real-time scrolling log of what the Auditor is doing right now. Auto-scrolls unless user clicks to pause. |
| **Running totals** | Counters that update live: resources found, eligible resources, estimated savings, zombies detected |
| **Elapsed time per phase** | Shows how long each phase took — useful for understanding scan duration for repeat scans |
| **Throttle indicator** | When AWS API rate limits are hit, the UI shows a visible indicator (not hidden — transparency builds trust) |
| **Pause / Resume** | Customer can pause the scan (e.g., if they're worried about API costs) and resume later. State is persisted. |
| **Cancel** | Customer can cancel at any time. Partial results are preserved and visible. |
| **Scan complete notification** | Browser notification + email when scan finishes (for large environments that take 10+ minutes) |

### 3.4 Audit Log File

Every action the Auditor takes is written to a **structured audit log** (JSON Lines format). This log is:

1. **Written in real-time** during the scan (not generated after the fact)
2. **Stored persistently** — available for download and dashboard review at any time
3. **Loadable into the Observability Dashboard** for historical analysis
4. **Exportable** as JSON or CSV for the customer's own compliance records

```jsonl
{"ts":"2027-03-15T14:22:03Z","phase":"enumeration","region":"us-east-1","service":"rds","action":"DescribeDBInstances","status":"started"}
{"ts":"2027-03-15T14:22:04Z","phase":"enumeration","region":"us-east-1","service":"rds","action":"DescribeDBInstances","status":"complete","resources_found":8,"duration_ms":1240}
{"ts":"2027-03-15T14:22:04Z","phase":"enumeration","region":"us-east-1","service":"rds","resource":"arn:aws:rds:us-east-1:123456789012:db:db-prod-main","type":"db.r6g.2xlarge","multi_az":true,"engine":"postgres","engine_version":"15.4"}
{"ts":"2027-03-15T14:26:38Z","phase":"ha_classify","service":"ec2","action":"DescribeInstances","status":"throttled","retry_after_ms":2400}
{"ts":"2027-03-15T14:26:40Z","phase":"ha_classify","service":"ec2","action":"DescribeInstances","status":"retried","attempt":2}
{"ts":"2027-03-15T14:30:12Z","phase":"cost_analysis","action":"GetCostAndUsage","status":"complete","period":"last_30_days","total_cost":87432.16}
```

**Log entry types:**
- `action_start` / `action_complete` — API call lifecycle
- `resource_discovered` — each resource found with its key metadata
- `throttle` — API rate limit events (shows transparency)
- `classification` — HA eligibility determination with reasoning
- `dependency_found` — connection between two resources
- `cost_attributed` — cost mapped to a specific resource
- `warning` — anything unusual (missing permissions, unexpected config, etc.)
- `error` — anything that failed (with retry info)

### 3.5 Scan History & Dashboard Integration

Every completed scan is saved with:
- Full audit log (JSON Lines)
- Scan summary (resource count, savings estimate, duration, errors)
- Generated report (Savings Report)
- Dependency graph snapshot

The dashboard shows:
- **Scan history list** — all past scans with date, duration, resource count, savings found
- **Scan comparison** — diff between two scans (what changed since last audit)
- **Log viewer** — load any past scan's log, filter by phase/service/severity, search
- **Replay mode** — step through a past scan's log entries with the progress UI (useful for demos or auditing SafeScale's own behavior)

---

## 4. Handling Edge Cases

### 4.1 Very Large Environments (5000+ Resources)

| Challenge | Solution |
|-----------|----------|
| API pagination | All Describe/List calls use pagination tokens. Never assume single-page results. |
| API rate limits | Per-service rate tracking with exponential backoff + jitter. Progress UI shows throttling transparently. |
| Scan duration | Parallel region scanning. Parallel service scanning within each region. Estimated time remaining shown in UI. |
| Memory usage | Stream results to database as discovered — don't hold all resources in memory. |
| Progress accuracy | Percentage is based on (completed API call groups / total API call groups), not resource count (which is unknown until enumeration completes). |

### 4.2 Partial Permissions

If the IAM role is missing some permissions (e.g., customer didn't deploy the full CloudFormation stack):

- The Auditor does NOT fail. It scans what it can and clearly reports what it couldn't access.
- The Progress UI shows: `⚠️ EKS: Access Denied — eks:DescribeCluster permission missing. EKS resources will not appear in this scan.`
- The Savings Report includes a "Permissions Gaps" section listing what was missed and estimated impact.
- A "Fix Permissions" button provides the exact IAM statement needed to fill the gap.

### 4.3 Cross-Account Resources

When the Auditor detects references to resources in other AWS accounts (e.g., VPC peering, cross-account RDS access):

- Flag as "External Dependency" in the topology graph
- Note: "This resource references account 987654321098 which is not connected to SafeScale"
- Offer a one-click onboarding link for the other account
- Never make assumptions about resources it can't see — only report what it can verify

### 4.4 Resources with No Cost Data

Some resources may not appear in Cost Explorer (newly created, or part of a bundled pricing model):

- Use published AWS pricing API as a fallback to estimate cost based on resource type and configuration
- Clearly mark estimated costs vs. actual billed costs in the report
- `💰 Actual (from Cost Explorer)` vs. `📊 Estimated (from AWS Pricing API)`

---

## 5. Optional Enrichment Sources — "Boost Your Scan"

### 5.1 Design Principle: Scan First, Enrich After

The Auditor's API-only scan is the **baseline that always works**. Enrichment sources are offered **after the initial scan completes** — never as a gate to starting. The customer sees their savings number first (the "aha moment"), then SafeScale offers: "Want more accurate results? Connect these optional sources."

This keeps onboarding fast (under 5 minutes to first results) while giving well-organized customers a path to higher-confidence findings.

### 5.2 Enrichment Source: IaC Repository (Terraform / OpenTofu / CloudFormation)

**Value: HIGH — strongly recommended**

Connect a Git repository (GitHub, GitLab, Bitbucket, or upload a zip) containing IaC definitions.

What the Auditor gains from IaC:

| Signal | How It Helps |
|--------|-------------|
| **Intended vs. actual state** | Compare Terraform state to live API data → reveals drift. Resources that drifted FROM Multi-AZ to Single-AZ (or vice versa) are flagged. This directly feeds Module 6 (Drift Detector). |
| **Environment distinctions** | Terraform workspaces, variable files (`prod.tfvars`, `staging.tfvars`), or directory structure (`/environments/prod/`, `/environments/dev/`) reveal which resources are production vs. non-production — critical for criticality classification. |
| **Module boundaries** | Terraform modules group related resources. If `module "checkout-service"` contains an RDS instance, an ECS service, and a Redis cluster, the Auditor knows these are part of the same logical service. |
| **Explicit dependencies** | Terraform resource references (`aws_ecs_service.app.depends_on`, `aws_security_group_rule` referencing another SG) give definitive dependency edges — upgrades dependency confidence from MEDIUM to HIGH. |
| **Variable-driven configs** | Variables like `multi_az = true` or `availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]` show which HA decisions were intentional vs. defaulted. |
| **Managed vs. unmanaged** | Resources in Terraform state are "managed." Resources found by the API but NOT in state are "unmanaged" — likely ClickOps, imported manually, or orphaned. This is valuable context. |

**Connection methods:**
- **Git repo** (preferred): OAuth integration with GitHub/GitLab/Bitbucket. SafeScale gets read-only access to the repo. Supports monorepos (customer specifies the path to infra code).
- **Upload**: Drag-and-drop a `.zip` of the IaC directory. For customers who can't grant repo access.
- **Terraform Cloud / Spacelift / env0 API**: Connect to their IaC automation platform to pull state files directly.

**What SafeScale reads:**
- `.tf` files (resource definitions, variables, outputs, modules)
- `.tfstate` or remote state (current resource mappings)
- `.tfvars` files (environment-specific configurations)
- `terragrunt.hcl` if Terragrunt is used

**What SafeScale does NOT read:**
- Application source code
- Secrets or sensitive variable values (they appear as `(sensitive)` in state)
- Anything outside the specified IaC directory

**Permission model:** Read-only repo access. SafeScale never commits, pushes, or modifies the repository.

**UI: Enrichment Impact Report**

After IaC ingestion, the Auditor re-scores findings and shows what changed:

```
┌──────────────────────────────────────────────────────────────────┐
│  IaC Enrichment Results — 142 Terraform-managed resources found  │
│                                                                  │
│  Confidence Upgrades:                                            │
│  ├── 23 resources upgraded from MEDIUM → HIGH confidence         │
│  ├── 8 resources upgraded from LOW → MEDIUM confidence           │
│  └── 3 dependency edges confirmed (were inferred)                │
│                                                                  │
│  New Findings:                                                   │
│  ├── 12 resources found in API but NOT in Terraform (unmanaged)  │
│  ├── 4 resources in Terraform but missing from API (stale state) │
│  ├── 2 environment distinctions discovered (prod vs staging)     │
│  └── 1 drift detected: redis-cache is Multi-AZ in AWS but       │
│      Single-AZ in Terraform (someone changed it manually)        │
│                                                                  │
│  Savings Estimate Updated: $16,840/mo → $18,210/mo (+$1,370)    │
│  (Higher confidence in 3 previously LOW-confidence resources)     │
│                                                                  │
│  [ View Updated Report → ]  [ View Drift Details → ]             │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Enrichment Source: Customer-Provided Context (Questionnaire)

**Value: MEDIUM — lightweight, always offered**

After the scan, present a short contextual questionnaire. Not a long form — a few targeted questions based on what the Auditor found. The questions are **dynamic** based on scan results.

**Example questions (generated from scan findings):**

```
┌──────────────────────────────────────────────────────────────────┐
│  Help us improve your results (optional — 2 minutes)             │
│                                                                  │
│  We found 8 RDS instances. Can you help us classify them?        │
│                                                                  │
│  db-prod-main (r6g.2xlarge, Multi-AZ, 94% peak CPU)             │
│  We think: Tier-1 (critical production)                          │
│  ○ Correct  ○ Actually Tier-2  ○ Actually Tier-3  ○ Not sure    │
│                                                                  │
│  db-analytics (r6g.xlarge, Multi-AZ, 12% peak CPU)              │
│  We think: Tier-2 (internal/batch)                               │
│  ○ Correct  ○ Actually Tier-1  ○ Actually Tier-3  ○ Not sure    │
│                                                                  │
│  db-staging-replica (r6g.large, Single-AZ, 3% peak CPU)         │
│  We think: Tier-3 (non-production)                               │
│  ○ Correct  ○ Actually Tier-2  ○ Not sure                       │
│                                                                  │
│  ──────────────────────────────────────────────────              │
│                                                                  │
│  What is your external SLA commitment to your customers?         │
│  ○ 99.5%  ○ 99.9%  ○ 99.95%  ○ 99.99%  ○ Other: ______        │
│                                                                  │
│  Which environments exist in this account?                       │
│  ☑ Production  ☑ Staging  ☐ Development  ☐ Sandbox  ☐ DR        │
│                                                                  │
│  [ Submit ]  [ Skip — use Auditor's best guesses ]               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key design rules:**
- Questions are **generated dynamically** from scan results — not a generic form
- Always skippable — the Auditor works without answers
- Shows what the Auditor already thinks (its inference) — the customer confirms or corrects
- Short — never more than 2 minutes to complete
- Answers upgrade confidence levels (LOW → MEDIUM, MEDIUM → HIGH)

### 5.4 Enrichment Source: Architecture Diagrams

**Value: LOW — accept but treat with caution**

Customers can optionally upload architecture diagrams. However, diagrams are treated as **LOW confidence hints**, never as ground truth, because:

- Diagrams are frequently outdated (the infrastructure evolved but the diagram didn't)
- Diagrams are often aspirational (showing intended architecture, not what's deployed)
- Diagrams may omit resources (only showing "important" services)
- Parsing is imprecise (diagram formats vary wildly)

**Accepted formats:**
- **draw.io / diagrams.net** (`.drawio`, `.xml`) — structured, parseable
- **Lucidchart export** (`.csv`, `.vsdx`) — structured
- **Image files** (`.png`, `.jpg`, `.svg`) — processed via vision AI to extract service names, connections, and topology hints
- **PDF** — processed similarly to images

**How diagrams are used:**
- Extract service names and groupings → attempt to match to discovered resources by name similarity
- Extract connection arrows → add as LOW confidence dependency hints
- Extract environment labels ("Production", "Staging") → use as naming hints for classification
- **Never override API-discovered data** — diagrams only add context where the API is ambiguous

**UI feedback:**
```
┌──────────────────────────────────────────────────────────────────┐
│  Diagram Analysis — architecture-v3.drawio                       │
│                                                                  │
│  Extracted: 24 service references, 31 connections                │
│  Matched to discovered resources: 18/24 (75%)                    │
│  Unmatched (diagram-only, not found in AWS): 6                   │
│    - "Legacy Auth Service" — no matching resource found           │
│    - "Planned Redis Cluster" — may not be deployed yet            │
│                                                                  │
│  ⚠️  Diagram confidence: LOW                                     │
│  These hints will be shown alongside API data but will not       │
│  override any API-confirmed findings.                            │
│                                                                  │
│  [ View Matched Resources → ]  [ Dismiss Diagram ]               │
└──────────────────────────────────────────────────────────────────┘
```

### 5.5 Enrichment Source Priority Summary

| Source | Value | When Offered | Blocks Scan? | Confidence Impact |
|--------|-------|-------------|-------------|-------------------|
| **AWS APIs** (core) | Required | Onboarding | N/A — this IS the scan | Baseline (HIGH for direct data, MEDIUM/LOW for inferred) |
| **IaC Repository** | HIGH | Post-scan, actively recommended | No | Many MEDIUM → HIGH upgrades. Reveals drift and unmanaged resources. |
| **Customer Questionnaire** | MEDIUM | Post-scan, always shown | No | Targeted LOW/MEDIUM → HIGH upgrades on specific resources. |
| **Architecture Diagrams** | LOW | Post-scan, available but not pushed | No | Minor hints only. Never overrides API data. |

### 5.6 Enrichment in the Progress UI

When enrichment sources are connected, the Auditor runs an additional enrichment phase:

```
│  PHASE 6: Report Generation                     ✅ Complete 0m08s │
│                                                                    │
│  ENRICHMENT PHASE (Optional)                    🔄 In Progress     │
│  ├── IaC Repository: parsing 142 .tf files .... 🔄 Scanning...    │
│  ├── Terraform state: matching to API resources  ⏳ Pending        │
│  ├── Customer questionnaire: 6/8 answered ...   ✅ Applied         │
│  └── Diagram: architecture-v3.drawio .......... ⏳ Pending         │
```

The enrichment phase re-scores findings and produces an **Enrichment Delta Report** showing exactly what changed and why.

---

## 6. Onboarding UX Flow — Screen by Screen

> Note: Enrichment sources (Section 5) are offered AFTER Screen 5 (Scan Complete). The onboarding flow below covers the core path — connect, scan, results. Enrichment is a separate follow-up step.

### Screen 1: Welcome

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   Welcome to SafeScale                                       │
│                                                              │
│   Let's see how much you're overpaying for                   │
│   cloud high availability.                                   │
│                                                              │
│   This takes under 5 minutes. We'll:                         │
│   1. Connect to your AWS account (read-only)                 │
│   2. Scan your infrastructure                                │
│   3. Show you exactly where you're overspending              │
│                                                              │
│   We never modify your infrastructure during the scan.       │
│   You can verify our permissions — they're 100% read-only.   │
│                                                              │
│   [ Connect AWS Account → ]                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Screen 2: Choose Connection Method

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   How would you like to connect?                             │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  ☁️  CloudFormation (Recommended)                     │   │
│   │  One-click deploy. Creates a read-only IAM role.     │   │
│   │  [ Launch Stack → ]                                  │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  🔧  Terraform / OpenTofu                             │   │
│   │  Copy our module into your IaC. Same permissions.    │   │
│   │  [ View Module → ]                                   │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  📋  Manual IAM Setup                                 │   │
│   │  Step-by-step instructions for creating the role.    │   │
│   │  [ View Instructions → ]                             │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  🏢  AWS Organizations (Multi-Account)                │   │
│   │  Deploy across all accounts via StackSet.            │   │
│   │  [ Setup StackSet → ]                                │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   🔒 View the exact IAM permissions we request              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Screen 3: Connection Test

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   Testing connection to AWS Account 123456789012...          │
│                                                              │
│   ✅ IAM Role assumption .............. Success              │
│   ✅ STS identity verified ............ Success              │
│   ✅ EC2 read access .................. Success              │
│   ✅ RDS read access .................. Success              │
│   ✅ ElastiCache read access .......... Success              │
│   ✅ EKS read access .................. Success              │
│   ✅ Cost Explorer access ............. Success              │
│   ⚠️  CloudWatch detailed metrics ..... Partial              │
│      (Some metrics require enhanced monitoring — optional)   │
│                                                              │
│   Connection successful! Ready to scan.                      │
│                                                              │
│   [ Start Audit Scan → ]    [ Fix Permissions ]              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Screen 4: Audit in Progress

*(See Section 3.2 — Progress UI Layout)*

### Screen 5: Scan Complete — Savings Summary

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ✅ Scan Complete — AWS Account 123456789012                │
│   Duration: 6m 42s  |  343 resources  |  3 regions           │
│                                                              │
│   ┌────────────────────────────────────────────────────────┐ │
│   │                                                        │ │
│   │   Your Monthly Cloud Bill:        $87,432              │ │
│   │   Eligible for Optimization:      $34,120  (39%)       │ │
│   │   Estimated Monthly Savings:      $16,840              │ │
│   │   Your Annual Savings:            $202,080             │ │
│   │                                                        │ │
│   │   SafeScale Fee (20%):            $3,368/mo            │ │
│   │   You Keep (80%):                 $13,472/mo           │ │
│   │                                                        │ │
│   └────────────────────────────────────────────────────────┘ │
│                                                              │
│   Top Savings Opportunities:                                 │
│   1. RDS db-prod-main (Multi-AZ) ........ $5,600/mo         │
│   2. EKS workers (3-AZ spread) .......... $4,200/mo         │
│   3. ElastiCache redis-session ........... $2,450/mo         │
│   4. RDS db-analytics (Multi-AZ) ........ $1,900/mo         │
│   5. EBS volumes (47 vols, ZRS) ......... $1,340/mo         │
│                                                              │
│   [ View Full Report → ]  [ Download PDF ]  [ View Log ]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. What the Auditor Does NOT Do

Drawing clear boundaries is as important as defining capabilities:

| The Auditor Does NOT... | Why |
|-------------------------|-----|
| Modify any AWS resource | Read-only by design. Trust is built on this guarantee. |
| **Require** Terraform / IaC state | Many customers don't use IaC. The Auditor works without it. IaC is an optional enrichment source (Section 5) that improves accuracy but is never mandatory. |
| Require tags or naming conventions | We read raw API metadata, not tags. |
| Modify or commit to IaC repositories | If connected, repos are read-only. SafeScale never pushes code. |
| Store customer data (DB contents, S3 objects, etc.) | We only read infrastructure metadata, billing data, and optionally IaC definitions. Zero customer data exfiltration. |
| Make final criticality decisions | It suggests tiers based on inference and enrichment. The customer confirms. |
| Override API data with diagram data | Diagrams are LOW confidence hints. API-discovered data always wins. |
| Auto-connect to additional accounts | Each account connection requires explicit customer action. |
| Share data between customers | Each customer's data is isolated. No cross-customer analytics on individual resources. |

---

## 7. Audit Accuracy & Confidence Levels

Every finding in the Audit Report includes a confidence indicator:

| Confidence | Meaning | Example |
|------------|---------|---------|
| **HIGH** | Verified from direct API data, or confirmed by IaC + API agreement, or confirmed by customer questionnaire | "RDS `db-prod-main` has `MultiAZ=true` — confirmed via `DescribeDBInstances`" |
| **MEDIUM** | Inferred from multiple signals, or upgraded from LOW via IaC context | "EKS `cluster-prod` workers span 3 AZs — inferred from subnet IDs in node group config" |
| **LOW** | Best-effort estimate, no corroborating source | "This EC2 ASG *likely* serves production traffic — based on high CPU utilization and ALB attachment, but no definitive signal" |

Enrichment sources (Section 5) upgrade confidence levels: IaC confirmation can upgrade MEDIUM → HIGH; customer questionnaire answers can upgrade LOW → MEDIUM or MEDIUM → HIGH; diagrams add context but never upgrade beyond LOW.

Resources classified with LOW confidence are highlighted in the UI and require explicit customer confirmation before any optimization proposal is generated.
