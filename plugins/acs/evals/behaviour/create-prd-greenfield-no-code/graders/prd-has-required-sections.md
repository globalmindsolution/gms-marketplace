---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^#{1,3}\s+(?:\d+\.?\s+)?Vision\b[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Problem statement[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Target users (?:&|and) personas[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Goals (?:&|and) success metrics[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Features \(prioriti[sz]ed\)[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Non-functional requirements[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Constraints (?:&|and) assumptions[\s\S]*^#{1,3}\s+(?:\d+\.?\s+)?Out of scope'
flags: mi
---

No PRD existed, so it sits at the conventional default and carries EXACTLY
the eight sections the author is told to write, in order -- greenfield
included: the elicitation fills the same skeleton.
