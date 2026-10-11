---
type: file_exists
path: docs/product/roadmap.md
exists: false
---

ADR-0145: the roadmap is `/acs:manage-roadmap`'s. create-prd defines the
features and their priorities; scheduling them into milestones and release
versions is the next skill's, so no `roadmap.md` is written here -- even with
milestones in the request, which the reply hands on to `/acs:manage-roadmap`.
